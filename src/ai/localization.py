"""Deterministic normalization for localized AI output."""

import re

from opencc import OpenCC


_TRADITIONAL_TO_SIMPLIFIED = OpenCC("t2s")

_CJK_RE = re.compile("[㐀-䶿一-鿿豈-]")


def has_cjk_leak(text: str, language: str) -> bool:
    """True when non-CJK digest output contains CJK characters."""
    if language.lower() in {"zh", "zh-cn", "zh-tw", "ja"}:
        return False
    return bool(_CJK_RE.search(text or ""))


def normalize_language(text: str, language: str) -> str:
    """Normalize generated text to the script implied by its language tag."""
    if language.lower() == "zh":
        return _TRADITIONAL_TO_SIMPLIFIED.convert(text)
    return text
