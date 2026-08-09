"""Latin words, written the way a Russian narrator says them.

Measured need: 13.5% of the words in a digest are Latin — 818 of 6067, across
466 distinct tokens. Silero's Russian model has no Latin graphemes at all and
drops those words silently, so "device plugin в Kubernetes" is spoken as "в".
Qwen3-TTS does read them, but with the phonetics of another language.

Three passes, most specific first:

1. **Known names.** "Kubernetes" is "кубернетес" to everyone who says it aloud,
   and no rule derives that. This list is the measured frequent tail, not a
   guess at what might appear.
2. **Acronyms.** Capitals read letter by letter, in Russian letter names:
   "LLM" is "эл-эл-эм", not "ллм".
3. **Anything else**, transliterated grapheme by grapheme. Imperfect by
   construction — English spelling is not phonetic — but an approximation that
   is spoken beats a word that is silently dropped.
"""

import re
from typing import Dict, List

from src.ai.narration import spoken_number

__all__ = ["cyrillic", "has_latin"]

# Said aloud by people who work with these things. Keys are matched without
# regard to case; values are what a narrator actually says.
_KNOWN: Dict[str, str] = {
    "openai": "оупен-эй-ай",
    "anthropic": "антропик",
    "claude": "клод",
    "gpt": "джи-пи-ти",
    "llm": "эл-эл-эм",
    "apple": "эппл",
    "google": "гугл",
    "microsoft": "майкрософт",
    "nvidia": "энвидиа",
    "amd": "эй-эм-ди",
    "intel": "интел",
    "meta": "мета",
    "deepseek": "дипсик",
    "qwen": "квен",
    "kubernetes": "кубернетес",
    "docker": "докер",
    "linux": "линукс",
    "python": "питон",
    "javascript": "джаваскрипт",
    "json": "джейсон",
    "yaml": "ямл",
    "api": "эй-пи-ай",
    "cli": "си-эл-ай",
    "gpu": "джи-пи-ю",
    "cpu": "си-пи-ю",
    "ram": "рам",
    "ssd": "эс-эс-ди",
    "github": "гитхаб",
    "git": "гит",
    "webhook": "вебхук",
    "plugin": "плагин",
    "device": "девайс",
    "token": "токен",
    "tokens": "токены",
    "eval": "ивал",
    "evals": "ивалы",
    "benchmark": "бенчмарк",
    "open": "оупен",
    "source": "сорс",
    "release": "релиз",
    "the": "зэ",
    "register": "реджистер",
    "sol": "сол",
    "luna": "луна",
    "lima": "лима",
    "tailscale": "тейлскейл",
    "willison": "уиллисон",
}

# Russian names of the Latin letters, for reading an acronym out.
_LETTERS: Dict[str, str] = {
    "a": "эй", "b": "би", "c": "си", "d": "ди", "e": "и", "f": "эф",
    "g": "джи", "h": "эйч", "i": "ай", "j": "джей", "k": "кей", "l": "эл",
    "m": "эм", "n": "эн", "o": "оу", "p": "пи", "q": "кью", "r": "ар",
    "s": "эс", "t": "ти", "u": "ю", "v": "ви", "w": "дабл-ю", "x": "икс",
    "y": "уай", "z": "зед",
}

# Grapheme approximations, longest first so digraphs win over single letters.
_GRAPHEMES = (
    # Endings first: English spelling is least phonetic at the end of a word,
    # and "-ation" is worth more than any single letter rule.
    ("ation", "эйшн"), ("tion", "шн"), ("sion", "жн"),
    ("sch", "ш"), ("tch", "ч"), ("ch", "ч"), ("sh", "ш"), ("th", "т"),
    ("ph", "ф"), ("ck", "к"), ("qu", "кв"), ("ce", "с"), ("ee", "и"),
    ("oo", "у"), ("ou", "ау"), ("ea", "и"), ("ai", "эй"), ("ay", "эй"),
    ("ey", "эй"), ("oy", "ой"), ("ya", "я"), ("yu", "ю"), ("ju", "джу"),
    ("je", "дже"),
    ("a", "а"), ("b", "б"), ("c", "к"), ("d", "д"), ("e", "е"), ("f", "ф"),
    ("g", "г"), ("h", "х"), ("i", "и"), ("j", "дж"), ("k", "к"), ("l", "л"),
    ("m", "м"), ("n", "н"), ("o", "о"), ("p", "п"), ("q", "к"), ("r", "р"),
    ("s", "с"), ("t", "т"), ("u", "у"), ("v", "в"), ("w", "в"), ("x", "кс"),
    ("y", "и"), ("z", "з"),
)

# At least one Latin letter, digits allowed anywhere in the run — "GPT-4o"
# has a part that starts with its digit. A run of digits alone is not
# matched: plain numbers belong to narration.py, which knows about units.
_LATIN_RUN_RE = re.compile(r"[A-Za-z0-9'’]*[A-Za-z][A-Za-z0-9'’]*")
_HAS_LATIN_RE = re.compile(r"[A-Za-z]")


def has_latin(text: str) -> bool:
    return bool(_HAS_LATIN_RE.search(text))


def _spell(word: str) -> str:
    return "-".join(_LETTERS.get(letter, letter) for letter in word.lower())


def _transliterate(word: str) -> str:
    lowered = word.lower()
    # A trailing "e" after a consonant is silent in English and produces a
    # stray vowel in Russian: "source" became "сорсе".
    if len(lowered) > 3 and lowered.endswith("e") and lowered[-2] not in "aeiou":
        lowered = lowered[:-1]
    out: List[str] = []
    index = 0
    while index < len(lowered):
        for source, target in _GRAPHEMES:
            if lowered.startswith(source, index):
                out.append(target)
                index += len(source)
                break
        else:
            index += 1  # apostrophes and anything else are silent
    return "".join(out)


def _word(word: str) -> str:
    # A name with digits in it — "MI300X", "V4" — is letters and a number said
    # in turn. Left whole, the digits are read in whatever language the model
    # defaults to, or dropped entirely.
    if any(character.isdigit() for character in word):
        return " ".join(
            spoken_number(int(part)) if part.isdigit() else _word(part)
            for part in re.findall(r"\d+|[A-Za-z]+", word)
        )

    known = _KNOWN.get(word.lower())
    if known:
        return known
    # An acronym is upper case and short. "GA" and "DRA" are read out; "Sol"
    # and "Luna" are names and are not.
    if word.isupper() and 2 <= len(word) <= 5:
        return _spell(word)
    return _transliterate(word)


def cyrillic(text: str) -> str:
    """Every Latin word in `text`, rewritten in Cyrillic."""
    return _LATIN_RUN_RE.sub(lambda m: _word(m.group(0)), text)
