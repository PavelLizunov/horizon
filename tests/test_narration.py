"""Narration text: what the speech model is given to read.

The number handling here is not decoration. Read with digits, the model
produced noticeably worse speech than the same sentences written out — that
comparison is what put this module in the repo, so the expansions are the part
worth pinning down.
"""

import pytest

from src.ai.narration import narration_text, speakable, spoken_date, spoken_number


def test_units_agree_with_their_number():
    """Russian units change with the count, and the teens break naive rules."""
    assert speakable("выплатить 567 млн долларов") == (
        "выплатить пятьсот шестьдесят семь миллионов долларов"
    )
    assert speakable("1 млн токенов") == "один миллион токенов"
    assert speakable("2 млн токенов") == "два миллиона токенов"
    # Known limit, pinned rather than pretended away: numerals come out in the
    # nominative, so a preposition that governs another case ("до ста двадцати
    # восьми тысяч") is not honoured. Fixing it means inferring case from
    # context — a parser, not a table — and the model reads the nominative
    # form intelligibly. Revisit only if it is audibly wrong.
    assert speakable("до 128 тыс. токенов") == "до сто двадцать восемь тысяч токенов"
    assert speakable("выросла на 15%") == "выросла на пятнадцать процентов"
    assert speakable("выросла на 1%") == "выросла на один процент"
    assert speakable("выросла на 3%") == "выросла на три процента"


def test_teens_take_the_many_form():
    # 11-14 end in 1-4 but take "many"; this is the case a hand-rolled rule
    # gets wrong.
    assert speakable("11 млн") == "одиннадцать миллионов"
    assert speakable("12%") == "двенадцать процентов"
    assert speakable("14 тыс.") == "четырнадцать тысяч"
    assert speakable("21 млн") == "двадцать один миллион"


def test_dates_are_spoken_in_the_genitive():
    assert spoken_date(6, "августа", 2026) == (
        "шестого августа две тысячи двадцать шестого года"
    )
    assert spoken_date(3, "мая", 2024) == "третьего мая две тысячи двадцать четвёртого года"
    assert speakable("вышел 6 августа 2026 года.") == (
        "вышел шестого августа две тысячи двадцать шестого года."
    )


def test_a_year_inside_a_date_is_not_read_as_a_cardinal():
    """Dates are expanded before plain numbers for exactly this reason."""
    spoken = speakable("релиз 6 августа 2026 года")
    assert "две тысячи двадцать шестого года" in spoken
    assert "две тысячи двадцать шесть" not in spoken


def test_bare_numbers_become_words():
    assert speakable("занятие длится 90 минут") == "занятие длится девяносто минут"


def test_reference_markers_and_urls_are_removed_without_stranding_punctuation():
    assert speakable("подтверждается релизами \\[tool-2-1\\]\\[tool-2-2\\].") == (
        "подтверждается релизами."
    )
    assert speakable("подробнее https://example.com/a/b тут") == "подробнее тут"


def test_shorthand_is_read_as_words():
    assert speakable("роботы, IoT и т.д.") == "роботы, IoT и так далее"


def test_narration_opens_with_the_date_and_never_the_profile():
    script = narration_text(
        "Заголовок",
        "Лид материала.",
        [("Контекст", "Текст контекста.")],
        date="2026-08-07",
    )

    assert script.startswith("седьмого августа. Заголовок.")
    assert "tech-news" not in script
    # Headings are glued to their first sentence: two-word inputs are where the
    # model ran away most.
    assert "Контекст. Текст контекста." in script


def test_empty_blocks_are_skipped():
    script = narration_text("Т", "Лид.", [("Пусто", ""), ("Есть", "Текст.")])
    assert "Пусто" not in script
    assert "Есть. Текст." in script


@pytest.mark.parametrize("value,expected", [(1, "один"), (128, "сто двадцать восемь")])
def test_spoken_number(value, expected):
    assert spoken_number(value) == expected
