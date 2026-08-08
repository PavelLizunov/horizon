"""Storage manager for configuration and state persistence."""

import html
import json
import os
import re
import shutil
from pathlib import Path
from typing import Any
from urllib.parse import quote

from pydantic import ValidationError

from .._file_utils import _atomic_write_text
from ..models import Config


# Matches ${VAR_NAME} in string config values. Names follow env-var rules
# (ASCII letters, digits, underscore; must not start with a digit).
_ENV_VAR_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


# Site pages live in the repo tree, not under data/, because the static-site
# generator reads from there. Anchored to this module rather than the working
# directory: launchd sets WorkingDirectory, but deploy/README.md also documents
# a crontab variant where a missing `cd` would silently relocate the whole site.
_REPO_ROOT = Path(__file__).resolve().parents[2]
SITE_DIGEST_DIR = _REPO_ROOT / "docs" / "digest"

# Digest pages are excluded from the search index on purpose. A year of daily
# digests measured 35 MB of search_index.json (4.6 MB gzipped) that every
# visitor downloads on first search; documentation-only search keeps it flat.
_SITE_FRONT_MATTER = "---\nsearch:\n  exclude: true\n---\n\n"


def _site_front_matter(title: str = "") -> str:
    """Front matter for a site page, carrying an explicit title when known.

    MkDocs derives a page title from its first H1, but an article's H1 is a
    markdown link followed by the score badge's raw `<span>`; it cannot parse a
    clean title out of that and silently falls back to the filename, so browser
    tabs and link previews read "Tech news 1". json.dumps produces a
    double-quoted scalar that is valid YAML whatever the title contains.
    """
    if not title:
        return _SITE_FRONT_MATTER
    return f"---\ntitle: {json.dumps(title, ensure_ascii=False)}\nsearch:\n  exclude: true\n---\n\n"


def safe_output_path(root: Path, filename: str) -> Path:
    """Return an output path only when it resolves below root."""
    resolved_root = root.resolve()
    candidate = (resolved_root / filename).resolve()
    if candidate.parent != resolved_root:
        raise ValueError(f"Output path escapes intended root: {candidate}")
    return candidate


def _expand_env_vars(value: Any) -> Any:
    """Recursively expand ``${VAR}`` references inside any string leaves.

    Containers (dicts, lists, tuples) are walked; non-string leaves are
    returned unchanged. Strings with no ``${...}`` tokens are returned
    unchanged. References to unset variables are **left as-is**, so
    ``${MISSING}`` round-trips to ``${MISSING}`` and surfaces as a clear
    downstream error rather than a silent empty string.

    This is intentionally identical to the behaviour ``RSSScraper`` uses
    for RSS feed URLs, so a single ``${VAR}`` convention works everywhere
    in the config (AI ``base_url``, feed URLs, webhook URLs, ...).
    """
    if isinstance(value, str):
        return _ENV_VAR_PATTERN.sub(
            lambda m: os.environ.get(m.group(1), m.group(0)),
            value,
        )
    if isinstance(value, dict):
        return {k: _expand_env_vars(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env_vars(v) for v in value]
    if isinstance(value, tuple):
        return tuple(_expand_env_vars(v) for v in value)
    return value


class ConfigError(ValueError):
    """Raised when configuration is missing or invalid."""

    pass


class StorageManager:
    """Manages file-based storage for configuration and state."""

    def __init__(self, data_dir: str = "data", config_path: str | None = None):
        self.data_dir = Path(data_dir)
        self.config_path = Path(config_path) if config_path is not None else self.data_dir / "config.json"
        self.summaries_dir = self.data_dir / "summaries"

        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.summaries_dir.mkdir(parents=True, exist_ok=True)

    def load_config(self) -> Config:
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {self.config_path}\n"
                f"Please create it based on the template in README.md"
            )

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ConfigError(
                f"Invalid JSON in configuration file: {self.config_path}\n" f"Error: {e}"
            ) from e

        # Expand ${VAR} references in every string value before pydantic
        # validation. Keeps credentials / private endpoints / tenant IDs
        # out of the JSON file so it is safe to commit to a public repo.
        data = _expand_env_vars(data)

        try:
            return Config.model_validate(data)
        except ValidationError as e:
            raise ConfigError(
                f"Configuration validation failed for {self.config_path}\n"
                f"Details: {e}"
            ) from e

    def save_config(self, config: Config, backup: bool = True) -> Path:
        """Save configuration to config.json, optionally backing up the existing file.

        Args:
            config: The Config object to save.
            backup: If True and config.json exists, copy it to config.json.bak first.

        Returns:
            Path to the saved config file.
        """
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        if backup and self.config_path.exists():
            shutil.copy2(self.config_path, self.config_path.with_suffix(".json.bak"))

        content = json.dumps(
            config.model_dump(mode="json"), indent=2, ensure_ascii=False
        )
        _atomic_write_text(self.config_path, f"{content}\n")

        return self.config_path

    def save_daily_summary(self, date: str, markdown: str, language: str = "en") -> Path:
        filename = f"horizon-{date}-{language}.md"
        filepath = safe_output_path(self.summaries_dir, filename)

        _atomic_write_text(filepath, markdown)

        return filepath

    def publish_site_pages(self, date: str, pages, language: str = "en") -> Path:
        """Write one page per article under `digest/{date}-{language}/`.

        Each article gets its own URL so a link from a chat message opens that
        article rather than dropping the reader into the middle of a long
        combined page. Deliberately not wrapped in a try/except: headline links
        point at these pages, so a silent failure would ship links to nothing.
        """
        # The issue directory name carries the language code, which is config —
        # validate it before mkdir, same as the page slugs below.
        issue_dir = safe_output_path(SITE_DIGEST_DIR, f"{date}-{language}")
        issue_dir.mkdir(parents=True, exist_ok=True)

        written: list[Path] = []
        for page in pages:
            filepath = safe_output_path(issue_dir, f"{page.slug}.md")
            _atomic_write_text(filepath, _site_front_matter(page.title) + page.markdown)
            written.append(filepath)

        self._write_site_index()
        return issue_dir

    @staticmethod
    def _write_site_index(limit: int = 60) -> None:
        """Regenerate the archive listing; `nav` in mkdocs.yml never sees these."""
        issues = sorted(
            (d for d in SITE_DIGEST_DIR.iterdir() if d.is_dir()),
            key=lambda d: d.name,
            reverse=True,
        )
        lines = ["# Архив выпусков", "", '<ul class="hz-archive">']
        for issue in issues[:limit]:
            count = sum(path.name != "index.md" for path in issue.glob("*.md"))
            name = html.escape(issue.name)
            href = quote(f"{issue.name}/index.md", safe="/-_.")
            lines.extend(
                [
                    "<li>",
                    f'<a href="{href}">',
                    f'<span class="hz-archive__date">{name}</span>',
                    '<span class="hz-archive__rule"></span>',
                    f'<span class="hz-archive__count">{count}</span>',
                    "</a>",
                    "</li>",
                ]
            )
        lines.append("</ul>")
        _atomic_write_text(
            SITE_DIGEST_DIR / "index.md", _SITE_FRONT_MATTER + "\n".join(lines) + "\n"
        )

    def load_subscribers(self) -> list:
        """Loads the list of email subscribers."""
        subscribers_path = self.data_dir / "subscribers.json"
        if not subscribers_path.exists():
            return []

        try:
            with open(subscribers_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return []

    def add_subscriber(self, email_addr: str):
        """Adds a new subscriber email."""
        subscribers = self.load_subscribers()
        if email_addr not in subscribers:
            subscribers.append(email_addr)
            self._save_subscribers(subscribers)

    def remove_subscriber(self, email_addr: str):
        """Removes a subscriber email."""
        subscribers = self.load_subscribers()
        if email_addr in subscribers:
            subscribers.remove(email_addr)
            self._save_subscribers(subscribers)

    def _save_subscribers(self, subscribers: list):
        """Helper to save subscribers list."""
        subscribers_path = self.data_dir / "subscribers.json"
        _atomic_write_text(subscribers_path, json.dumps(subscribers, indent=2))
