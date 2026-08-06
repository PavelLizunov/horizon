"""Deterministic normalization for localized AI output."""

import re

from opencc import OpenCC


_TRADITIONAL_TO_SIMPLIFIED = OpenCC("t2s")

# Escapes, not literal characters: this class previously ended in "豈-", where
# the trailing hyphen is a *literal* hyphen rather than the start of a range —
# so every ordinary dash matched and any hyphenated word counted as a CJK leak.
# The compatibility-ideograph range had lost its upper bound.
#   U+3400–U+4DBF  CJK Unified Ideographs Extension A
#   U+4E00–U+9FFF  CJK Unified Ideographs
#   U+F900–U+FAFF  CJK Compatibility Ideographs
_CJK_RE = re.compile("[㐀-䶿一-鿿豈-﫿]")


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
