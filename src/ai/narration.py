"""Turn a rendered article into prose a speech model can read aloud.

Two jobs, both measured rather than assumed.

**Stripping.** Reference markers, URLs and markdown escaping are silent on the
page but noise in speech. They come out.

**Numbers.** This one earned its place by listening: the same sentences read
with digits and with every number written out are noticeably different, and the
written-out take is the one that sounds like a person. So digits are expanded
here rather than left to the model — "567 млн долларов" becomes "пятьсот
шестьдесят семь миллионов долларов", and a date becomes the genitive a Russian
speaker actually says.

Russian agreement is why this is not a one-liner: the unit after a number
changes with the number ("один миллион", "два миллиона", "пять миллионов"), and
dates need ordinals in the genitive. Generating the numerals themselves is a
solved library problem, so `num2words` does that part; the agreement rules,
which it does not cover, are here.

Known limit: numerals come out in the nominative. A preposition that governs
another case — "до 128 тыс." is properly "до ста двадцати восьми тысяч" —
is not honoured, because inferring case from context needs a parser rather than
a table. The nominative reads intelligibly, so this stays until it is audibly
wrong on real text.
"""

import re
from typing import Iterable, List, Sequence, Tuple

from num2words import num2words

__all__ = ["narration_text", "speakable", "spoken_number", "spoken_date"]


# Reference markers the analyst leaves in prose, e.g. "…2026 года [tool-2-1]".
# The optional backslashes matter: summaries frozen in data/summaries/ store the
# markdown-escaped shape, and matching only the bare one left "\ \ ." in speech.
_REFERENCE_RE = re.compile(r"[ \t]*(?:\\?\[[^\]]*\\?\])+")
_URL_RE = re.compile(r"\(?https?://\S+\)?")
_MARKDOWN_ESCAPE_RE = re.compile(r"\\(?=[\s.,;:!?)]|$)")
_RULE_RE = re.compile(r"(?m)^\s*-{3,}\s*$")
_WHITESPACE_RE = re.compile(r"[ \t]+")
_SPACE_BEFORE_PUNCTUATION_RE = re.compile(r"\s+([.,;:!?])")

MONTHS = (
    "января февраля марта апреля мая июня июля августа "
    "сентября октября ноября декабря"
).split()

# Written shorthand that a reader says as words. Ordered longest-first so that
# "т.д." is not eaten by a shorter key.
_SHORTHAND: Sequence[Tuple[str, str]] = (
    ("т. е.", "то есть"),
    ("т.е.", "то есть"),
    ("т. д.", "так далее"),
    ("т.д.", "так далее"),
    ("т. п.", "тому подобное"),
    ("т.п.", "тому подобное"),
    ("гг.", "годов"),
    ("др.", "другие"),
)

# Number + unit, where the unit has to agree with the number.
_UNITS = {
    "млрд": ("миллиард", "миллиарда", "миллиардов"),
    "млн": ("миллион", "миллиона", "миллионов"),
    "тыс.": ("тысяча", "тысячи", "тысяч"),
    "тыс": ("тысяча", "тысячи", "тысяч"),
    "%": ("процент", "процента", "процентов"),
}
_NUMBER_UNIT_RE = re.compile(
    r"(?<![\w])(\d[\d\s\u00a0]*)\s*(млрд|млн|тыс\.?|%)(?![\w])"
)
_DATE_RE = re.compile(rf"(?<![\d])(\d{{1,2}})\s+({'|'.join(MONTHS)})\s+(\d{{4}})\s+года")
_BARE_NUMBER_RE = re.compile(r"(?<![\w\d.,-])(\d{1,12})(?![\w\d.,])")


def _plural(count: int, one: str, few: str, many: str) -> str:
    """Pick the Russian form that agrees with `count`.

    The teens are the exception that catches every naive implementation: 11–14
    take the "many" form despite ending in 1–4.
    """
    tail = abs(count) % 100
    if 11 <= tail <= 14:
        return many
    tail %= 10
    if tail == 1:
        return one
    if 2 <= tail <= 4:
        return few
    return many


def _genitive(ordinal: str) -> str:
    """Nominative masculine ordinal to genitive: `шестой` -> `шестого`.

    num2words only produces the nominative, and a spoken date needs the
    genitive throughout — "шестого августа две тысячи двадцать шестого года".
    """
    if ordinal.endswith("ий"):  # третий -> третьего
        return ordinal[:-2] + "ьего"
    if ordinal.endswith(("ый", "ой")):
        return ordinal[:-2] + "ого"
    return ordinal


def spoken_number(value: int) -> str:
    """Digits as words, in the nominative."""
    return num2words(value, lang="ru")


def spoken_date(day: int, month: str, year: int) -> str:
    """`6 августа 2026 года` in the case a person actually says it."""
    day_words = _genitive(num2words(day, lang="ru", to="ordinal"))
    year_words = _genitive(num2words(year, lang="ru", to="ordinal"))
    return f"{day_words} {month} {year_words} года"


def _expand_units(text: str) -> str:
    def replace(match: re.Match) -> str:
        digits = re.sub(r"[\s\u00a0]", "", match.group(1))
        unit = match.group(2).rstrip(".") if match.group(2) != "%" else "%"
        forms = _UNITS.get(match.group(2)) or _UNITS.get(unit)
        if forms is None:
            return match.group(0)
        count = int(digits)
        return f"{spoken_number(count)} {_plural(count, *forms)}"

    return _NUMBER_UNIT_RE.sub(replace, text)


def _expand_dates(text: str) -> str:
    return _DATE_RE.sub(
        lambda m: spoken_date(int(m.group(1)), m.group(2), int(m.group(3))), text
    )


def _expand_bare(text: str) -> str:
    return _BARE_NUMBER_RE.sub(lambda m: spoken_number(int(m.group(1))), text)


def speakable(text: str) -> str:
    """One passage, cleaned and with its numbers written out."""
    text = _RULE_RE.sub(" ", text)
    text = _URL_RE.sub(" ", text)
    text = _REFERENCE_RE.sub("", text)
    text = _MARKDOWN_ESCAPE_RE.sub("", text)
    text = text.replace("\u00a0", " ")
    for written, spoken in _SHORTHAND:
        text = text.replace(written, spoken)
    # Dates first: they contain a bare year that the plain-number pass would
    # otherwise read as a cardinal ("две тысячи двадцать шесть года").
    text = _expand_dates(text)
    text = _expand_units(text)
    text = _expand_bare(text)
    text = _WHITESPACE_RE.sub(" ", text)
    text = _SPACE_BEFORE_PUNCTUATION_RE.sub(r"\1", text)
    return text.strip()


def narration_text(
    title: str,
    lede: str,
    blocks: Iterable[Tuple[str, str]],
    *,
    date: str = "",
) -> str:
    """The full script for one article.

    The date opens the reading because it is the one thing a listener cannot
    see. The profile id does not: "tech-news" is our plumbing, the same
    objection that took it out of the byline on the page.
    """
    opening = ""
    if date:
        _, month, day = date.split("-")
        spoken_day = _genitive(num2words(int(day), lang="ru", to="ordinal"))
        opening = f"{spoken_day} {MONTHS[int(month) - 1]}. "

    parts: List[str] = [f"{opening}{speakable(title)}.".strip(), "", speakable(lede)]
    for heading, body in blocks:
        if not body:
            continue
        # The heading is glued to its first sentence rather than left alone:
        # two-word inputs are where this model ran away most often.
        parts += ["", f"{speakable(heading)}. {speakable(body)}"]
    return "\n".join(part for part in parts if part is not None).strip() + "\n"
