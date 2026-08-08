import json
from types import SimpleNamespace
from typing import cast

import pytest
from pathlib import Path
import src._file_utils as file_utils
import src.storage.manager as manager
from src.storage.manager import StorageManager, ConfigError, _expand_env_vars, safe_output_path
from src.models import AIConfig, Config
from pydantic import ValidationError

def test_load_config_missing_file(tmp_path):
    storage = StorageManager(data_dir=str(tmp_path))
    with pytest.raises(FileNotFoundError):
        storage.load_config()

def test_load_config_invalid_json(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text("invalid json", encoding="utf-8")
    
    storage = StorageManager(data_dir=str(tmp_path))
    with pytest.raises(ConfigError) as excinfo:
        storage.load_config()
    assert "Invalid JSON in configuration file" in str(excinfo.value)
    assert str(config_path) in str(excinfo.value)

def test_load_config_validation_failure(tmp_path):
    config_path = tmp_path / "config.json"
    # Missing required 'ai' and 'sources' fields
    config_path.write_text(json.dumps({}), encoding="utf-8")
    
    storage = StorageManager(data_dir=str(tmp_path))
    with pytest.raises(ConfigError) as excinfo:
        storage.load_config()
    assert "Configuration validation failed" in str(excinfo.value)
    assert str(config_path) in str(excinfo.value)

def test_load_config_success(tmp_path):
    config_path = tmp_path / "config.json"
    config_data = {
        "ai": {
            "provider": "anthropic",
            "model": "claude-3-sonnet",
            "api_key_env": "ANTHROPIC_API_KEY"
        },
        "sources": {
            "hackernews": {"enabled": True}
        },
        "collection": {
            "time_window_hours": 24
        }
    }
    config_path.write_text(json.dumps(config_data), encoding="utf-8")
    
    storage = StorageManager(data_dir=str(tmp_path))
    config = storage.load_config()
    assert config.collection.time_window_hours == 24
    assert config.ai.provider == "anthropic"


@pytest.mark.parametrize(
    ("legacy_key", "legacy_value"),
    [
        ("version", "2.0"),
        ("filtering", {"time_window_hours": 24}),
    ],
)
def test_config_rejects_removed_top_level_fields(legacy_key, legacy_value):
    data = {
        "ai": {
            "provider": "openai",
            "model": "test",
            "api_key_env": "OPENAI_API_KEY",
        },
        "sources": {},
        legacy_key: legacy_value,
    }

    with pytest.raises(ValidationError):
        Config.model_validate(data)


def test_custom_config_path_overrides_data_directory(tmp_path):
    config_path = tmp_path / "config" / "custom.json"
    storage = StorageManager(
        data_dir=str(tmp_path / "data"),
        config_path=str(config_path),
    )

    assert storage.config_path == config_path


def test_save_config_creates_custom_config_parent(tmp_path):
    config_path = tmp_path / "config" / "nested" / "custom.json"
    storage = StorageManager(
        data_dir=str(tmp_path / "data"),
        config_path=str(config_path),
    )
    config = cast(Config, SimpleNamespace(model_dump=lambda mode: {"example": "value"}))

    assert storage.save_config(config) == config_path
    assert json.loads(config_path.read_text(encoding="utf-8")) == {"example": "value"}


class TestExpandEnvVars:
    """Recursive ${VAR} expansion on config dicts/lists/strings."""

    def test_expands_simple_reference(self, monkeypatch):
        monkeypatch.setenv("FOO", "bar")
        assert _expand_env_vars("prefix-${FOO}-suffix") == "prefix-bar-suffix"

    def test_expands_multiple_references_in_one_string(self, monkeypatch):
        monkeypatch.setenv("A", "1")
        monkeypatch.setenv("B", "2")
        assert _expand_env_vars("${A}/${B}") == "1/2"

    def test_leaves_unset_var_as_placeholder(self, monkeypatch):
        monkeypatch.delenv("MISSING", raising=False)
        assert _expand_env_vars("${MISSING}") == "${MISSING}"

    def test_ignores_non_matching_patterns(self):
        assert _expand_env_vars("no braces here") == "no braces here"
        assert _expand_env_vars("$FOO without braces") == "$FOO without braces"
        assert _expand_env_vars("${123INVALID}") == "${123INVALID}"

    def test_recurses_into_dict(self, monkeypatch):
        monkeypatch.setenv("HOST", "api.example.com")
        result = _expand_env_vars({"url": "https://${HOST}/v1", "port": 443})
        assert result == {"url": "https://api.example.com/v1", "port": 443}

    def test_recurses_into_list(self, monkeypatch):
        monkeypatch.setenv("X", "hi")
        assert _expand_env_vars(["${X}", "plain", 7]) == ["hi", "plain", 7]

    def test_preserves_non_string_leaves(self):
        assert _expand_env_vars(42) == 42
        assert _expand_env_vars(3.14) == 3.14
        assert _expand_env_vars(True) is True
        assert _expand_env_vars(None) is None

    def test_deeply_nested(self, monkeypatch):
        monkeypatch.setenv("TOKEN", "secret")
        value = {
            "a": [
                {"b": "Bearer ${TOKEN}"},
                {"b": ["${TOKEN}", 1]},
            ],
        }
        out = _expand_env_vars(value)
        assert out["a"][0]["b"] == "Bearer secret"
        assert out["a"][1]["b"] == ["secret", 1]


def test_load_config_expands_env_vars_in_ai_base_url(tmp_path, monkeypatch):
    """Integration: proves base_url is env-expandable end-to-end.

    This is exactly the use case that keeps private/tenant endpoint
    URLs out of version control.
    """
    monkeypatch.setenv("HORIZON_AI_BASE_URL", "https://private-proxy.example/v1")
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({
        "ai": {
            "provider": "openai",
            "model": "gpt-4o",
            "api_key_env": "OPENAI_API_KEY",
            "base_url": "${HORIZON_AI_BASE_URL}",
        },
        "sources": {"hackernews": {"enabled": True}},
        "collection": {"time_window_hours": 24},
    }), encoding="utf-8")

    storage = StorageManager(data_dir=str(tmp_path))
    config = storage.load_config()
    assert config.ai.base_url == "https://private-proxy.example/v1"


@pytest.mark.parametrize("language", ["en", "zh-CN", "pt_BR", "sr-Latn-RS"])
def test_ai_config_accepts_normal_language_codes(language):
    config = AIConfig(provider="openai", model="gpt-4o", api_key_env="OPENAI_API_KEY", languages=[language])
    assert config.languages == [language]


@pytest.mark.parametrize("language", ["../outside", "en/../../outside", "en\\outside", ".", ""])
def test_ai_config_rejects_unsafe_language_codes(language):
    with pytest.raises(ValidationError):
        AIConfig(provider="openai", model="gpt-4o", api_key_env="OPENAI_API_KEY", languages=[language])


def test_save_daily_summary_defensively_rejects_path_escape(tmp_path):
    storage = StorageManager(data_dir=str(tmp_path / "data"))
    with pytest.raises(ValueError, match="escapes intended root"):
        storage.save_daily_summary("2026-07-13", "secret", language="../../../../outside")
    assert not (tmp_path / "outside.md").exists()


def _pages(*pairs):
    """(slug, markdown) pairs as minimal page objects for publish_site_pages."""
    return [
        SimpleNamespace(slug=slug, markdown=markdown, title=f"Title {slug}")
        for slug, markdown in pairs
    ]


def test_publish_site_pages_keeps_the_h1_and_excludes_from_search(tmp_path, monkeypatch):
    monkeypatch.setattr(manager, "SITE_DIGEST_DIR", tmp_path / "digest")
    storage = StorageManager(data_dir=str(tmp_path / "data"))

    issue_dir = storage.publish_site_pages(
        "2026-08-06", _pages(("tech-news-1", "# Digest Ninitux\n\nbody\n")), language="ru"
    )
    written = (issue_dir / "tech-news-1.md").read_text(encoding="utf-8")

    assert issue_dir.name == "2026-08-06-ru"
    # Excluding digests is what keeps search_index.json from growing without
    # bound — a year of them measured 4.6 MB gzipped.
    assert "search:\n  exclude: true" in written.split("---")[1]
    # An explicit title: MkDocs cannot parse one out of an H1 that is a link
    # plus a score badge, and silently falls back to the filename.
    assert '"Title tech-news-1"' in written
    # The H1 itself must still survive verbatim.
    assert "# Digest Ninitux" in written
    assert "body" in written


def test_publish_site_pages_refreshes_the_index_newest_first(tmp_path, monkeypatch):
    monkeypatch.setattr(manager, "SITE_DIGEST_DIR", tmp_path / "digest")
    storage = StorageManager(data_dir=str(tmp_path / "data"))

    storage.publish_site_pages("2026-08-05", _pages(("a", "# a")), language="ru")
    storage.publish_site_pages("2026-08-06", _pages(("b", "# b")), language="ru")
    index = (tmp_path / "digest" / "index.md").read_text(encoding="utf-8")

    assert index.index("2026-08-06-ru") < index.index("2026-08-05-ru")
    assert 'href="2026-08-06-ru/"' in index
    # The listing must not link to the top-level index it lives in.
    assert 'href="index.md"' not in index and "](index.md)" not in index


def test_site_index_rows_carry_a_date_and_a_count(tmp_path, monkeypatch):
    """Rows used to be the raw directory name, language suffix and all.

    Every row then looked identical — `2026-08-07-ru` — with nothing to choose
    between them and no sign of how much was in any issue.
    """
    monkeypatch.setattr(manager, "SITE_DIGEST_DIR", tmp_path / "digest")
    storage = StorageManager(data_dir=str(tmp_path / "data"))

    storage.publish_site_pages(
        "2026-08-06", _pages(("a", "# a"), ("b", "# b")), language="ru"
    )
    index = (tmp_path / "digest" / "index.md").read_text(encoding="utf-8")

    assert '<span class="hz-archive__date">2026-08-06</span>' in index
    # The issue's own index page is not one of its articles.
    assert '<span class="hz-archive__count">2</span>' in index


def test_publish_site_pages_rejects_path_escape(tmp_path, monkeypatch):
    monkeypatch.setattr(manager, "SITE_DIGEST_DIR", tmp_path / "digest")
    storage = StorageManager(data_dir=str(tmp_path / "data"))

    with pytest.raises(ValueError, match="escapes intended root"):
        storage.publish_site_pages("2026-08-06", _pages(("a", "x")), language="../../../../outside")
    assert not (tmp_path / "outside.md").exists()

    # The slug is validated the same way.
    with pytest.raises(ValueError, match="escapes intended root"):
        storage.publish_site_pages("2026-08-06", _pages(("../../../../outside", "x")), language="ru")
    assert not (tmp_path / "outside").exists()


def test_publish_site_pages_replace_failure_preserves_destination(tmp_path, monkeypatch):
    monkeypatch.setattr(manager, "SITE_DIGEST_DIR", tmp_path / "digest")
    storage = StorageManager(data_dir=str(tmp_path / "data"))
    issue_dir = storage.publish_site_pages("2026-08-06", _pages(("a", "# existing")), language="ru")
    destination = issue_dir / "a.md"

    def fail_replace(source, target):
        raise OSError("replace failed")

    monkeypatch.setattr(file_utils.os, "replace", fail_replace)

    with pytest.raises(OSError, match="replace failed"):
        storage.publish_site_pages("2026-08-06", _pages(("a", "# replacement")), language="ru")

    assert "# existing" in destination.read_text(encoding="utf-8")
    assert list(destination.parent.glob(f".{destination.name}.*.tmp")) == []


def test_safe_output_path_rejects_escape_from_other_output_roots(tmp_path):
    with pytest.raises(ValueError, match="escapes intended root"):
        safe_output_path(tmp_path / "docs" / "_posts", "../../../outside.md")


def test_save_daily_summary_replace_failure_preserves_destination(tmp_path, monkeypatch):
    storage = StorageManager(data_dir=str(tmp_path))
    destination = storage.save_daily_summary("2026-07-13", "existing")

    def fail_replace(source, target):
        raise OSError("replace failed")

    monkeypatch.setattr(file_utils.os, "replace", fail_replace)

    with pytest.raises(OSError, match="replace failed"):
        storage.save_daily_summary("2026-07-13", "replacement")

    assert destination.read_text(encoding="utf-8") == "existing"
    assert list(destination.parent.glob(f".{destination.name}.*.tmp")) == []


def test_save_subscribers_replace_failure_preserves_destination(tmp_path, monkeypatch):
    storage = StorageManager(data_dir=str(tmp_path))

    def fail_replace(source, target):
        raise OSError("replace failed")

    monkeypatch.setattr(file_utils.os, "replace", fail_replace)

    subscribers_path = tmp_path / "subscribers.json"
    subscribers_path.write_text('["old"]', encoding="utf-8")
    with pytest.raises(OSError, match="replace failed"):
        storage._save_subscribers(["new"])

    assert subscribers_path.read_text(encoding="utf-8") == '["old"]'
    assert list(tmp_path.glob(f".{subscribers_path.name}.*.tmp")) == []


def test_article_pages_carry_an_explicit_title(tmp_path, monkeypatch):
    """MkDocs cannot derive a title from an H1 that is a link plus a badge span.

    Without this the page title falls back to the filename, so browser tabs and
    link previews read "Tech news 1" instead of the article's headline.
    """
    monkeypatch.setattr(manager, "SITE_DIGEST_DIR", tmp_path / "digest")
    storage = StorageManager(data_dir=str(tmp_path / "data"))
    page = SimpleNamespace(
        slug="tech-news-1",
        title='Смена руководства: "кавычки" и двоеточие',
        markdown="# [T](https://e.com) <span>9.0</span>\n",
    )

    storage.publish_site_pages("2026-08-06", [page], language="ru")
    written = (tmp_path / "digest" / "2026-08-06-ru" / "tech-news-1.md").read_text(
        encoding="utf-8"
    )

    assert written.startswith("---\ntitle: ")
    assert "Смена руководства" in written.split("---")[1]
