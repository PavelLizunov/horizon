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

import hashlib
import html
import re
from typing import Iterable, List, Sequence, Tuple

from num2words import num2words

__all__ = [
    "attach_player",
    "audio_key",
    "chunks",
    "coverage",
    "reached_the_end",
    "narration_text",
    "speakable",
    "speech_ends_at",
    "spoken_number",
    "spoken_date",
    "tera_text",
]


# Reference markers the analyst leaves in prose, e.g. "…2026 года [tool-2-1]".
# The optional backslashes matter: summaries frozen in data/summaries/ store the
# markdown-escaped shape, and matching only the bare one left "\ \ ." in speech.
_REFERENCE_RE = re.compile(r"[ \t]*(?:\\?\[[^\]]*\\?\])+")
_BARE_REFERENCE_RE = re.compile(r"(?<!\w)tool-\d+(?:-\d+)+(?!\w)", re.IGNORECASE)
_EMPTY_PARENS_RE = re.compile(r"\(\s*(?:,\s*)*\)")
_URL_RE = re.compile(r"\(?https?://\S+\)?")
_MARKDOWN_ESCAPE_RE = re.compile(r"\\(?=[\s`*_{}\[\]()#+\-.!,;:?|]|$)")
_RULE_RE = re.compile(r"(?m)^\s*-{3,}\s*$")
# A section heading that reaches the model is not read as a heading — a stray
# "## Блоги" at the end of an article came back as twenty seconds the recogniser
# rendered "Продолжение следует…". The whole line goes, not just the hashes:
# a heading with nothing under it has nothing to introduce.
_HEADING_RE = re.compile(r"(?m)^[ \t]*#{1,6}[ \t]+.*$")
_WHITESPACE_RE = re.compile(r"[ \t]+")
_SPACE_BEFORE_PUNCTUATION_RE = re.compile(r"\s+([.,;:!?])")

MONTHS = (
    "января февраля марта апреля мая июня июля августа "
    "сентября октября ноября декабря"
).split()

# Comparison operators, said aloud. Longest first, so ">=" is not read as ">"
# followed by a stray "=". These have to go: TeraTTS takes "<" and ">" for
# language tags and refuses the whole passage, so "llm>=0.32" in one article
# cost it its narration outright.
_COMPARISONS: Sequence[Tuple[str, str]] = (
    (">=", " не ниже "),
    ("<=", " не выше "),
    ("=>", " не ниже "),
    ("=<", " не выше "),
    (">", " больше "),
    ("<", " меньше "),
)

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

# Acronyms, said letter by letter in Russian letter names. A run of capitals is
# not a word, and each voice invents its own way through one — a listener put it
# as "it read the abbreviations very oddly". Whole English words are left alone:
# the model reads those well, and transliterating them was tried and rejected.
#
# Not applied next to a digit, so "MI300X" and "GPT-4o" stay whole; those are
# product names rather than initials.
_ACRONYM_RE = re.compile(r"(?<![A-Za-z0-9])[A-Z]{2,6}(?![A-Za-z0-9])")

# The ones people say as a word instead of spelling out. Measured from the
# archive rather than imagined: these are the caps runs that actually appear.
_SAID_AS_WORDS = {
    "JSON": "джейсон",
    "YAML": "ямл",
    "KEDA": "кеда",
    "QEMU": "кему",
    "CUDA": "куда",
    "REST": "рест",
    "SAAS": "саас",
}

_LETTER_NAMES = {
    "A": "эй", "B": "би", "C": "си", "D": "ди", "E": "и", "F": "эф",
    "G": "джи", "H": "эйч", "I": "ай", "J": "джей", "K": "кей", "L": "эл",
    "M": "эм", "N": "эн", "O": "оу", "P": "пи", "Q": "кью", "R": "ар",
    "S": "эс", "T": "ти", "U": "ю", "V": "ви", "W": "дабл-ю", "X": "икс",
    "Y": "уай", "Z": "зед",
}


def _spell_acronyms(text: str) -> str:
    def replace(match: re.Match) -> str:
        word = match.group(0)
        said = _SAID_AS_WORDS.get(word)
        if said:
            return said
        return "-".join(_LETTER_NAMES.get(letter, letter) for letter in word)

    return _ACRONYM_RE.sub(replace, text)


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
# The trailing hyphen in the lookahead matters. Without it, only the first
# number of a hyphenated identifier was expanded: the legal citation
# "NMSA 1978 § 30-8-1" was read as "§ тридцать-8-1", because "30" matched and
# "8" and "1" were then blocked by the lookbehind. Either every part is a word
# or none is, and for an identifier none is right.
#
# `[.,]\d` rather than a bare `[.,]`: blocking on any following period meant a
# number that ended a sentence was never expanded at all. "Prometheus-порт
# 31995." went to the model as digits, and digits are what it reads with
# Chinese phonetics. Only a period with a digit after it is a decimal point.
_BARE_NUMBER_RE = re.compile(r"(?<![\w\d.,-])(\d{1,12})(?![\w\d-]|[.,]\d)")

# Versions and decimals: "v1.34", "GPT-5.6", "$0,20". A listener hears "один
# точка тридцать четыре"; the model, left to itself, reads the digits in
# another language entirely. Expanded before plain numbers, so the two halves
# are not taken for separate cardinals.
#
# The lookahead has the same shape as the bare-number one, and for the same
# reason: "до v1.36," was left as digits because a comma followed it. A comma
# or period only continues a number when a digit comes after it.
_DECIMAL_RE = re.compile(
    r"(?<![\d.,])(\d+)[.,](\d+)(?:(rc|a|b)(\d+))?(?!\d|[.,]\d)",
    re.IGNORECASE,
)


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


def _expand_decimals(text: str) -> str:
    def replace(match: re.Match) -> str:
        # "v1.34" would otherwise come out "vодин точка тридцать четыре", one
        # word the model has to guess at. A version marker is a word of its own
        # once the number beside it is one.
        start = match.start()
        lead = " " if start and text[start - 1].isalpha() else ""
        whole, part = int(match.group(1)), int(match.group(2))
        result = f"{lead}{spoken_number(whole)} точка {spoken_number(part)}"
        suffix, suffix_number = match.group(3), match.group(4)
        if suffix:
            suffix_name = {"rc": "эр-си", "a": "альфа", "b": "бета"}[suffix.lower()]
            result += f" {suffix_name} {spoken_number(int(suffix_number))}"
        return result

    return _DECIMAL_RE.sub(replace, text)


# A currency sign is read, not skipped, and it sits before its number where the
# unit rules expect one after. Left alone it glued itself to the expanded
# number — "$ноль точка двадцать" — which is no better than the digits were.
# The scale word is part of the match, not left for the unit rule: taking
# "$567" on its own turned "$567 млн" into "пятьсот шестьдесят семь долларов
# млн", with the scale stranded after the currency it was scaling.
_DOLLARS_RE = re.compile(r"\$(\d+(?:[.,]\d+)?)(?:\s*(млрд|млн|тыс\.?))?")


def _expand_currency(text: str) -> str:
    def replace(match: re.Match) -> str:
        amount, scale = match.group(1), match.group(2)
        if "." in amount or "," in amount:
            whole, part = re.split(r"[.,]", amount, maxsplit=1)
            # A fractional amount takes the genitive singular whatever the
            # digits say — "один точка двадцать доллара", never "доллар".
            return (
                f"{spoken_number(int(whole))} точка {spoken_number(int(part))} доллара"
            )
        count = int(amount)
        if scale:
            forms = _UNITS[scale] if scale in _UNITS else _UNITS[scale.rstrip(".")]
            return f"{spoken_number(count)} {_plural(count, *forms)} долларов"
        return f"{spoken_number(count)} {_plural(count, 'доллар', 'доллара', 'долларов')}"

    return _DOLLARS_RE.sub(replace, text)


def _expand_bare(text: str) -> str:
    return _BARE_NUMBER_RE.sub(lambda m: spoken_number(int(m.group(1))), text)


# Tera reads most ordinary English words well even inside a Russian sentence,
# so a blanket transliterator makes the archive worse. This deliberately small
# lexicon contains names that were distorted or dropped in an A/B synthesis of
# the real voice, plus product spellings whose digits cannot be guessed. It is
# Tera-only: Qwen reads the original English better and keeps receiving it.
_TERA_PRONUNCIATIONS: Sequence[Tuple[str, str]] = (
    ("/v1/chat/completions", "ви один, чат комплишнс"),
    ("Day-2-сценарии", "сценарии второго дня"),
    ("claude-sonnet-5", "Клод Соннет пять"),
    ("claude-fable-5", "Клод Фэйбл пять"),
    ("claude-opus-5", "Клод Опус пять"),
    ("k8s-dra-driver", "кей восемь эс ди-ар-эй драйвер"),
    ("джи-пи-ти-4o-mini", "джи-пи-ти четыре-оу мини"),
    ("gpt-4o-mini", "джи-пи-ти четыре-оу мини"),
    ("gpt-image-2", "джи-пи-ти имидж два"),
    ("Gemma4-31B", "Гемма четыре, тридцать один миллиард параметров"),
    ("ди-эй-эл-эл-E", "далли"),
    ("дабл-ю-эй-эс-эм", "васм"),
    ("эн-ви-ай-ди-ай-эй", "энвидиа"),
    ("ар-и-эй-ди-эм-и", "ридми"),
    ("джи-пи-ти-4o", "джи-пи-ти четыре-оу"),
    ("эн-эй-эс-эй", "наса"),
    ("Claude Code", "Клод Код"),
    ("Hugging Face", "Хаггинг Фэйс"),
    ("Hacker News", "Хакер Ньюс"),
    ("MiniMax-H3", "Минимакс эйч три"),
    ("Os8088", "Оу-эс восемь тысяч восемьдесят восемь"),
    ("PostgreSQL", "Постгрес-кью-эл"),
    ("Muse Glimmer", "Мьюз Глиммер"),
    ("HackerOne", "Хакер Уан"),
    ("Shieldstral", "Шилдстрал"),
    ("ChatGPT", "Чат-джи-пи-ти"),
    ("MI300X", "эм-ай триста икс"),
    ("5800H", "пять тысяч восемьсот эйч"),
    ("Border0", "Бордер зиро"),
    ("OpenAI", "Оупен Эй-Ай"),
    ("GitHub", "Гитхаб"),
    ("Claude", "Клод"),
    ("Codex", "Кодекс"),
    ("Qwen", "Квэн"),
    ("Muse", "Мьюз"),
    ("Zen6", "Зен шесть"),
    ("8bit", "восемь бит"),
    ("12c", "двенадцать си"),
    ("4o", "четыре-оу"),
    ("4K", "четыре ка"),
    ("3D", "три дэ"),
    ("2x", "два икс"),
)
_TERA_PRONUNCIATION_BY_SOURCE = {
    source.casefold(): spoken for source, spoken in _TERA_PRONUNCIATIONS
}
_TERA_PRONUNCIATION_RE = re.compile(
    r"(?<![A-Za-zА-Яа-яЁё0-9])(?:"
    + "|".join(
        re.escape(source)
        for source, _ in sorted(_TERA_PRONUNCIATIONS, key=lambda item: -len(item[0]))
    )
    + r")(?![A-Za-zА-Яа-яЁё0-9])",
    re.IGNORECASE,
)
_TERA_MODEL_SIZE_RE = re.compile(
    r"(?<!\w)(\d+)B-(модел[А-Яа-яЁё]*)(?!\w)", re.IGNORECASE
)
_TERA_PARAMETER_COUNT_RE = re.compile(
    r"(?<!\w)(\d+)B(?=$|[^\w])(?:\s+параметров|-(?=[А-Яа-яЁё]))?",
    re.IGNORECASE,
)
_TERA_SCALE_SUFFIX_RE = re.compile(r"(?<!\w)(\d+)([kM])(?!\w)")
_TERA_ACRONYM_NUMBER_RE = re.compile(
    r"(?<![A-Za-z0-9])([A-Z]{1,6})(\d+)(?![A-Za-z0-9])"
)
_TERA_ACRONYM_NUMBER_ACRONYM_RE = re.compile(
    r"(?<![A-Za-z0-9])([A-Z]{1,6})(\d+)([A-Z]{1,6})(?![A-Za-z0-9])"
)
_TERA_X_NUMBER_RE = re.compile(r"(?<!\w)x(\d+)(?!\w)", re.IGNORECASE)
_TERA_CROSS_SCRIPT_RE = re.compile(
    r"(?<=[A-Za-z0-9])[-/.](?=[А-Яа-яЁё])|"
    r"(?<=[А-Яа-яЁё])[-/.](?=[A-Za-z0-9])"
)


def tera_text(text: str) -> str:
    """Prepare already-normalised prose specifically for Russian TeraTTS."""
    text = _TERA_PRONUNCIATION_RE.sub(
        lambda match: _TERA_PRONUNCIATION_BY_SOURCE[match.group(0).casefold()], text
    )

    def model_size(match: re.Match) -> str:
        count = int(match.group(1))
        scale = _plural(count, "миллиард", "миллиарда", "миллиардов")
        return f"{match.group(2)} на {spoken_number(count)} {scale} параметров"

    def parameter_count(match: re.Match) -> str:
        count = int(match.group(1))
        scale = _plural(count, "миллиард", "миллиарда", "миллиардов")
        separator = " " if match.group(0).endswith("-") else ""
        return f"{spoken_number(count)} {scale} параметров{separator}"

    def scaled_number(match: re.Match) -> str:
        count = int(match.group(1))
        forms = (
            ("тысяча", "тысячи", "тысяч")
            if match.group(2) == "k"
            else ("миллион", "миллиона", "миллионов")
        )
        return f"{spoken_number(count)} {_plural(count, *forms)}"

    def acronym_number(match: re.Match) -> str:
        letters = "-".join(_LETTER_NAMES[letter] for letter in match.group(1))
        return f"{letters} {spoken_number(int(match.group(2)))}"

    def acronym_number_acronym(match: re.Match) -> str:
        before = "-".join(_LETTER_NAMES[letter] for letter in match.group(1))
        after = "-".join(_LETTER_NAMES[letter] for letter in match.group(3))
        return f"{before} {spoken_number(int(match.group(2)))} {after}"

    text = _TERA_MODEL_SIZE_RE.sub(model_size, text)
    text = _TERA_PARAMETER_COUNT_RE.sub(parameter_count, text)
    text = _TERA_SCALE_SUFFIX_RE.sub(scaled_number, text)
    text = _TERA_ACRONYM_NUMBER_ACRONYM_RE.sub(acronym_number_acronym, text)
    text = _TERA_ACRONYM_NUMBER_RE.sub(acronym_number, text)
    text = _TERA_X_NUMBER_RE.sub(
        lambda match: f"икс {spoken_number(int(match.group(1)))}", text
    )
    # A Russian suffix glued to an unknown Latin base is one token to the model.
    # Keep the English spelling, which Tera usually handles, but give each script
    # its own word. Slashes and dots have the same failure shape as hyphens.
    text = _TERA_CROSS_SCRIPT_RE.sub(" ", text)
    return _WHITESPACE_RE.sub(" ", text).strip()


def speakable(text: str) -> str:
    """One passage, cleaned and with its numbers written out."""
    text = _RULE_RE.sub(" ", text)
    text = _HEADING_RE.sub(" ", text)
    text = _URL_RE.sub(" ", text)
    text = _REFERENCE_RE.sub("", text)
    text = _BARE_REFERENCE_RE.sub("", text)
    text = _MARKDOWN_ESCAPE_RE.sub("", text)
    text = _EMPTY_PARENS_RE.sub("", text)
    # "admission-webhook&\#x27;\u0438" reached the model spelled out, entity and
    # backslash and all. The summariser escapes for HTML and then for markdown,
    # and neither pass is undone on the way to speech: the markdown rule above
    # only strips a backslash before punctuation, and "#" is not punctuation to
    # it. Both come off here, in that order, because the backslash is what stops
    # the entity being recognised.
    text = text.replace("\\#", "#")
    text = html.unescape(text)
    # Comparison operators are read, not skipped — and one of them stopped a
    # reading dead: TeraTTS takes "<" and ">" for language tags, so a version
    # constraint like "llm>=0.32" raised "invalid language tags" and cost that
    # article its narration. Unescaping above can also put a bare "<" back into
    # the text, which is the same hazard by another route.
    for symbol, spoken in _COMPARISONS:
        text = text.replace(symbol, spoken)
    text = text.replace("\u00a0", " ")
    for written, spoken in _SHORTHAND:
        text = text.replace(written, spoken)
    # Dates first: they contain a bare year that the plain-number pass would
    # otherwise read as a cardinal ("две тысячи двадцать шесть года").
    text = _expand_dates(text)
    text = _spell_acronyms(text)
    text = _expand_currency(text)
    text = _expand_units(text)
    text = _expand_decimals(text)
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


_WORD_RE = re.compile(r"[\w-]+", re.UNICODE)


_SPELLED_ACRONYM_RE = re.compile(
    "(?:" + "|".join(sorted(set(_LETTER_NAMES.values()), key=len, reverse=True)) + ")"
    "(?:-(?:" + "|".join(sorted(set(_LETTER_NAMES.values()), key=len, reverse=True)) + "))+"
)
_NAME_TO_LETTER = {name: letter.lower() for letter, name in _LETTER_NAMES.items()}
_NAME_RE = re.compile(
    "|".join(sorted(set(_LETTER_NAMES.values()), key=len, reverse=True))
)


def _unspell(text: str) -> str:
    """Turn a spelled-out acronym back into its letters: "джи-пи-ю" -> "gpu".

    Only for comparison. The pipeline writes acronyms out so they are said
    correctly; a recogniser hears them and writes "GPU" straight back. Without
    this the two never match and the score falls for a reading that was right —
    which is exactly what happened when acronym spelling was introduced, and it
    took the coverage of a sound article from 0.84 to 0.73.
    """
    # Matched by name rather than split on hyphens: "дабл-ю" is one letter and
    # contains one, so splitting tore it in half and raised KeyError('дабл') on
    # the first article with a W in an acronym.
    return _SPELLED_ACRONYM_RE.sub(
        lambda m: "".join(_NAME_TO_LETTER[name] for name in _NAME_RE.findall(m.group(0))),
        text,
    )


def _words(text: str) -> List[str]:
    """The words of a passage, as something worth comparing.

    ё folds to е. Russian writes both for the same sound and transcribers are
    inconsistent about it — "остаётся" came back as "остается" and cost real
    points, which is the measurement being wrong about the audio rather than the
    audio being wrong.
    """
    return _WORD_RE.findall(_unspell(text.lower().replace("ё", "е")))


def coverage(source: str, heard: str) -> float:
    """How much of what we asked for is actually in what was spoken, 0…1.

    Duration is too weak a check on its own. A narration that stopped early and
    filled the rest with noise measured 204 seconds against 237 expected — well
    inside any sane tolerance, and unusable: the speech broke off mid-sentence
    and the last 23 seconds were babble that a transcriber rendered as
    "Продолжение следует…".

    Comparing the words a recogniser heard against the words we sent catches
    that, and it is an independent check: a different model grading the first
    one, rather than the generator judging itself.

    Recall over a multiset rather than a diff ratio, because a recogniser
    reorders nothing but does mishear: missing content is what matters, and an
    occasional wrong word should not read as a failure.
    """
    wanted = _words(source)
    if not wanted:
        return 1.0
    available: dict[str, int] = {}
    for word in _words(heard):
        available[word] = available.get(word, 0) + 1

    found = 0
    for word in wanted:
        if available.get(word, 0):
            available[word] -= 1
            found += 1
    return found / len(wanted)


def reached_the_end(source: str, heard: str, words: int = 10) -> float:
    """How much of the *end* of the text was actually spoken, 0…1.

    Plain coverage over every word turned out to measure the wrong thing on
    short pieces: a recogniser mishearing two words out of eighty costs more
    than truncation does, and the score never cleared a threshold that
    truncation would fail. Measured on real chunks it topped out at 0.92 for
    takes that were perfectly complete.

    The failure being hunted is always the same shape — the reading stops
    early and the rest is noise — so look at the end specifically. If the last
    words of the source appear anywhere in the transcript, the reading got
    there; if it broke off, they cannot be there at all.

    Only the tail words that occur nowhere else in the text count. Ordinary
    ones ("в", "этом", "тут") were being matched against text the model had read
    minutes earlier, which scored a reading that broke off halfway at 0.5 —
    within reach of passing. A word that appears exactly once can only have come
    from the end.
    """
    said = _words(source)
    tail = said[-words:]
    if not tail:
        return 1.0

    seen: dict[str, int] = {}
    for word in said:
        seen[word] = seen.get(word, 0) + 1
    # Fall back to the whole tail when the ending repeats itself and there is
    # nothing distinctive to key on.
    distinctive = [word for word in tail if seen[word] == 1] or tail

    spoken = set(_words(heard))
    return sum(1 for word in distinctive if word in spoken) / len(distinctive)


# A real reading runs at roughly eleven characters a second. Anything slower
# than three is not speech: that is the shape of a hallucinated tail — a long
# segment holding almost no text, which a transcriber renders as "Продолжение
# следует…" over twenty seconds of babble.
_SPEECH_CHARS_PER_SECOND = 3


def speech_ends_at(segments: Iterable[dict]) -> float:
    """The timestamp where real speech stops, in seconds.

    Trusting the last segment's end is what let trailing noise through: the
    transcriber happily timestamps babble. Judging each segment by how much text
    it holds per second separates a spoken sentence from a held breath.

    Returns 0.0 when nothing in the recording looks like speech.
    """
    end = 0.0
    for segment in segments:
        span = max(segment["end"] - segment["start"], 0.01)
        if len(segment["text"].strip()) / span > _SPEECH_CHARS_PER_SECOND:
            end = segment["end"]
    return end


def audio_key(issue: str, slug: str, audio: bytes) -> str:
    """The object-storage key for a narration, digest and all.

    The name carries a hash of the audio, so re-narrating an article publishes a
    new address. Without that the `immutable` cache header on the audio host is a
    lie: it promises the bytes at this address never change, and overwriting the
    object left every cache — browser and edge — serving the old take forever.

    Same trick the theme uses for its own assets, and the reason those can be
    cached for a year.
    """
    return f"{issue}/{slug}-{hashlib.sha256(audio).hexdigest()[:10]}.opus"


_PLAYER_MARKER = 'class="hz-narration"'
_BYLINE_OPEN = '<p class="hz-byline">'


def attach_player(markdown: str, url: str, seconds: float) -> str:
    """Put the player into a published page, under the byline.

    Under the byline because the choice to listen instead of read is made before
    reading, not after.

    Re-running must not stack players, so any existing one is removed first —
    re-narrating an article is routine, and the second pass has the better audio.

    Raises ValueError when there is no byline to anchor to; a page that silently
    gains no player is a narration that quietly went nowhere.
    """
    if _PLAYER_MARKER in markdown:
        kept: List[str] = []
        for line in markdown.split("\n"):
            if _PLAYER_MARKER in line:
                # The blank line that separates the player from the byline goes
                # with it. Leaving it behind made every re-narration add one
                # more empty line, so a page that changed in no visible way
                # still came back as a diff.
                if kept and not kept[-1].strip():
                    kept.pop()
                continue
            kept.append(line)
        markdown = "\n".join(kept)

    index = markdown.find(_BYLINE_OPEN)
    if index == -1:
        raise ValueError("no byline in the page; nothing to anchor the player to")
    end = markdown.index("</p>", index) + len("</p>")

    minutes = max(1, round(seconds / 60))
    player = (
        f'<audio {_PLAYER_MARKER} controls preload="none" '
        f'src="{url}" aria-label="Озвучка статьи, {minutes} мин"></audio>'
    )
    return markdown[:end] + "\n\n" + player + markdown[end:]


# Chunk sizes, from measurement and from other people's bug reports. A whole
# article in one generation produced one clean file in seven; the clean one was
# also the shortest. Qwen3-TTS is known for it — mlx-audio #464 reports speech
# dropping out of the middle, and QwenLM #239 reports the speaking rate drifting
# on anything past a hundred characters. Short pieces sidestep all of it.
#
# The floor matters as much as the ceiling: two-word inputs were where the model
# ran away most often, producing eleven seconds of noise from nine characters.
#
# The ceiling came down from 700 on a listener's judgement, and the measurement
# I had disagreed with them. Shorter pieces score *worse* on spread of speaking
# rate — x3.36 against x2.06 — but that is not what a listener hears. What they
# hear is whether it is the same person throughout, and shorter pieces are
# steadier there: the random state is reset for every piece, so a short one has
# less room to drift from the character it started with.
#
# 400 is the floor of what is safe, not a preference. Swept over the whole
# archive: at 400 no piece falls under the floor; at 300 eleven do; at 200 the
# smallest piece is three characters, which is the runaway case exactly.
MAX_CHUNK_CHARS = 400
MIN_CHUNK_CHARS = 120


_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?…])\s+")


def _pack(sentences: List[str], limit: float) -> List[str]:
    """Whole sentences into pieces of at most `limit` characters.

    A sentence longer than the limit goes out on its own and over-long: a cut
    anywhere but a sentence boundary is audible, and the ceiling is the softer
    of the two constraints. A sentence that would leave the piece under the
    floor is taken anyway — a piece below the floor is the worse failure.
    """
    pieces: List[str] = []
    for sentence in sentences:
        if not pieces:
            pieces.append(sentence)
            continue
        joined = f"{pieces[-1]} {sentence}"
        room = len(joined) <= limit or len(pieces[-1]) < MIN_CHUNK_CHARS
        if room and len(joined) <= MAX_CHUNK_CHARS:
            pieces[-1] = joined
        else:
            pieces.append(sentence)
    return pieces


def chunks(text: str) -> List[str]:
    """Split narration into pieces a speech model completes reliably.

    Sentences are the unit — a cut anywhere else is audible — and they are packed
    into pieces of even size rather than filled to the ceiling one after another.

    Even sizes are the point. Filling greedily and gluing the leftovers made
    pieces that broke both bounds at once: a real article came out
    `[717, 773, 6]`, over the ceiling twice and with a six-character tail sent to
    the model on its own, which is the input that produced eleven seconds of
    noise. Dividing the text into `ceil(total / MAX)` pieces of roughly equal
    length cannot do that: no piece reaches the ceiling unless a single sentence
    already exceeds it, and there is no leftover to strand.
    """
    sentences: List[str] = []
    # splitlines() rather than a "\n\n" split: it handles CRLF, which arrives
    # whenever the text half of the pipeline runs on Windows and which a
    # "\n\n" split silently turns into one unbreakable block.
    paragraphs: List[str] = []
    current: List[str] = []
    for line in text.splitlines():
        if line.strip():
            current.append(line.strip())
        elif current:
            paragraphs.append(" ".join(current))
            current = []
    if current:
        paragraphs.append(" ".join(current))

    for paragraph in paragraphs:
        sentences += [part for part in _SENTENCE_SPLIT_RE.split(paragraph) if part]
    if not sentences:
        return []

    # Packed twice. The first pass fills to the ceiling and so answers "how few
    # pieces can this be"; the second spreads the same text evenly over exactly
    # that many. Deriving the share from the text length alone does not work:
    # a piece closes on a sentence boundary and so lands under its share every
    # time, the shortfall accumulates, and the last piece is left with whatever
    # is over — one article came out …, 399, 286, 122 against a ceiling of 400.
    total = len(" ".join(sentences))
    pieces = _pack(sentences, MAX_CHUNK_CHARS)
    # Repeat until the count settles: a smaller share can need one more piece
    # than the count it was derived from, and then the share is wrong again.
    # Three passes is enough on everything in the archive; the guard is against
    # a text that oscillates rather than a text that needs more.
    for _ in range(3):
        spread = _pack(sentences, total / len(pieces))
        if len(spread) == len(pieces):
            pieces = spread
            break
        pieces = spread

    # Even division leaves no stranded tail in the ordinary case, but the
    # remainder still lands in the last piece and can fall under the floor.
    if len(pieces) > 1 and len(pieces[-1]) < MIN_CHUNK_CHARS:
        tail = pieces.pop()
        if len(pieces[-1]) + 1 + len(tail) <= MAX_CHUNK_CHARS:
            pieces[-1] = f"{pieces[-1]} {tail}"
        else:
            # Too big to absorb, so move sense the other way: the piece before
            # it gives up whole sentences until the tail is worth speaking on
            # its own — but never so many that the donor falls under the floor
            # in its place.
            donors = _SENTENCE_SPLIT_RE.split(pieces[-1])
            while (
                len(tail) < MIN_CHUNK_CHARS
                and len(donors) > 1
                and len(" ".join(donors[:-1])) >= MIN_CHUNK_CHARS
            ):
                tail = f"{donors.pop()} {tail}"
            pieces[-1] = " ".join(donors)
            pieces.append(tail)
    return pieces
