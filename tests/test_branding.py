"""The digest's name has one home.

It used to be written out in five unrelated files, and one of them — the
Feishu card builder — bypassed the label table entirely, so renaming the
digest was guaranteed to leave a stale copy behind somewhere. These tests
fail when a new hardcode appears, which is the only way that stays true.
"""

import re
from pathlib import Path

import pytest

from src.ai.summarizer import DEFAULT_BRAND, DailySummarizer
from src.models import DigestConfig
from pydantic import ValidationError

REPO = Path(__file__).resolve().parents[1]

# The three places the literal is allowed: the shared fallback, the config
# default that owns the setting, and the e-mail sender name (its own setting,
# because the From: line is not always the digest's name).
ALLOWED = {
    Path("src/ai/summarizer.py"): 1,
    Path("src/models.py"): 2,
}


def _python_sources():
    for directory in ("src", "scripts"):
        for path in sorted((REPO / directory).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            yield path


def test_the_brand_literal_appears_only_where_it_is_defined():
    offenders = {}
    for path in _python_sources():
        count = path.read_text(encoding="utf-8").count(DEFAULT_BRAND)
        if not count:
            continue
        relative = path.relative_to(REPO)
        if ALLOWED.get(relative, 0) != count:
            offenders[str(relative)] = count

    assert not offenders, (
        "the digest name is hardcoded outside its definitions: "
        f"{offenders}. Read it from `config.digest.brand`, or from "
        "`DEFAULT_BRAND` when no config is in reach."
    )


def test_summarizer_uses_the_configured_brand_everywhere_it_names_itself():
    summarizer = DailySummarizer(brand="Утренник")
    pages = summarizer.build_article_pages([], "2026-08-08", language="ru")

    index = pages[-1]
    assert index.markdown.startswith("# Утренник - 2026-08-08")
    assert index.title == "Утренник - 2026-08-08"
    assert DEFAULT_BRAND not in index.markdown


def test_summarizer_falls_back_to_the_shared_default():
    assert DailySummarizer().brand == DEFAULT_BRAND


def test_digest_config_carries_the_brand_and_rejects_an_empty_one():
    assert DigestConfig().brand == DEFAULT_BRAND
    assert DigestConfig(brand="  Утренник  ").brand == "Утренник"
    with pytest.raises(ValidationError):
        DigestConfig(brand="   ")


def test_no_language_carries_its_own_name():
    """A name is a name in every language.

    `LABELS` used to hold a per-language "header", which meant the zh digest
    called itself something else and a rename had to touch three entries.
    """
    from src.ai.summarizer import LABELS

    assert not any("header" in labels for labels in LABELS.values())


def test_the_site_chrome_and_the_document_agree_on_the_name():
    """mkdocs.yml is the one place outside Python that names the site.

    It cannot read `data/config.json`, so it keeps its own copy — this test
    exists so the two cannot drift silently.
    """
    mkdocs = (REPO / "mkdocs.yml").read_text(encoding="utf-8")
    match = re.search(r"(?m)^site_name:\s*(.+?)\s*$", mkdocs)
    assert match, "mkdocs.yml has no site_name"
    assert match.group(1) == DEFAULT_BRAND, (
        f"mkdocs.yml says {match.group(1)!r} while the digest says "
        f"{DEFAULT_BRAND!r}; rename both together."
    )


def test_narration_player_has_one_controller_on_every_screen():
    player = (REPO / "docs/assets/horizon-player.js").read_text(encoding="utf-8")

    assert "function PlayerController(audio)" in player
    assert 'document.querySelector("audio.hz-narration")' in player
    assert 'createElement("audio")' not in player
    assert "matchMedia" not in player
    assert "nativeRateControl" not in player
    assert "−10" in player
    assert "+15" in player
    assert "IntersectionObserver" in player


def test_narration_player_uses_native_inputs_and_keeps_a_fallback():
    player = (REPO / "docs/assets/horizon-player.js").read_text(encoding="utf-8")
    css = (REPO / "docs/assets/horizon-digest.css").read_text(encoding="utf-8")

    assert 'seek.type = "range"' in player
    assert 'document.createElement("select")' in player
    assert "var SPEEDS = [0.75, 1, 1.25, 1.5, 1.75, 2, 2.5]" in player
    assert "VOLUME_KEY" not in player
    assert "RESUME_PREFIX" in player
    assert "mediaSession" in player
    assert 'typeof menu.showPopover === "function"' in player
    assert 'menu.popover = "auto"' in player
    assert 'event.key === "Escape"' in player
    assert 'event.key === "ArrowDown"' in player
    assert 'menu.matches(":popover-open")' in player
    assert '"hz-player__volume--open"' in player
    assert ".hz-player__volume::before" in css
    assert "@media screen and (min-width: 600px)" in css
    assert 'classList.toggle("hz-player--visible", visible)' in player
    assert "this.sticky.inert = !visible" in player
    assert "env(safe-area-inset-bottom)" in css
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert player.index('document.body.appendChild(this.sticky)') < player.index(
        'this.audio.removeAttribute("controls")'
    )
    assert re.search(r"catch \(error\) \{\s*this\.destroy\(\);\s*throw error", player)
