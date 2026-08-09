"""Narration text: what the speech model is given to read.

The number handling here is not decoration. Read with digits, the model
produced noticeably worse speech than the same sentences written out — that
comparison is what put this module in the repo, so the expansions are the part
worth pinning down.
"""

import pytest

from src.ai.narration import (
    MAX_CHUNK_CHARS,
    MIN_CHUNK_CHARS,
    attach_player,
    audio_key,
    chunks,
    coverage,
    narration_text,
    reached_the_end,
    speakable,
    speech_ends_at,
    spoken_date,
    spoken_number,
)


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


def test_a_section_heading_never_reaches_the_model():
    """A stray "## Блоги" at the end of one article came back as twenty seconds
    the transcriber rendered "Продолжение следует…"."""
    assert speakable("Последняя мысль.\n\n## Блоги") == "Последняя мысль."
    assert speakable("### Заголовок\n\nТекст.") == "Текст."
    # A hash that is not a heading marker stays: no space, no heading.
    assert "#Т" in speakable("тег #Тема тут")


def test_a_number_that_ends_a_sentence_is_still_spoken():
    """The lookahead blocked on any following period, so a number at the end of
    a sentence was never expanded — and digits are what the model reads with
    Chinese phonetics. Only a period with a digit after it is a decimal point."""
    assert speakable("Prometheus-порт 31995.") == (
        "Prometheus-порт тридцать одна тысяча девятьсот девяносто пять."
    )
    assert speakable("их было 5, потом больше") == "их было пять, потом больше"


def test_versions_and_decimals_are_spoken():
    assert speakable("Kubernetes v1.34+") == "Kubernetes v один точка тридцать четыре+"
    assert speakable("GPT-5.6 Sol") == "GPT-пять точка шесть Sol"
    assert speakable("версия 2.0 вышла") == "версия два точка ноль вышла"


def test_punctuation_after_a_version_does_not_block_it():
    """"до v1.36," stayed as digits because a comma followed. A separator only
    continues a number when a digit comes after it."""
    assert speakable("gate до v1.36, дальше") == "gate до v один точка тридцать шесть, дальше"
    assert speakable("GPT-5.6.") == "GPT-пять точка шесть."
    # Three parts is a version string, not a decimal; left whole on purpose.
    assert speakable("версия 1.2.3 вышла") == "версия 1.2.3 вышла"


def test_a_version_marker_does_not_glue_itself_to_the_number():
    """"v1.34" became "vодин точка…" — one word the model has to guess at."""
    assert " один точка" in speakable("до v1.36")


def test_dollars_are_read_as_a_word():
    assert speakable("$5 в месяц") == "пять долларов в месяц"
    assert speakable("цена $0,20 за токен") == "цена ноль точка двадцать доллара за токен"


def test_a_scale_word_stays_with_the_money_it_scales():
    """Taking "$567" alone stranded the scale: "пятьсот шестьдесят семь
    долларов млн"."""
    assert speakable("выплатить $567 млн за вред") == (
        "выплатить пятьсот шестьдесят семь миллионов долларов за вред"
    )


def test_escaped_entities_never_reach_the_model():
    """"admission-webhook&\\#x27;и" was read out entity and backslash and all —
    the summariser escapes for HTML and then for markdown, and nothing undid
    either on the way to speech."""
    assert speakable("admission-webhook&\\#x27;и") == "admission-webhook'и"
    assert speakable("Rock &amp; Roll") == "Rock & Roll"


def test_a_hyphenated_identifier_is_left_alone():
    """All of it becomes words or none of it does. Expanding only the first part
    read "NMSA 1978 § 30-8-1" aloud as "§ тридцать-8-1"."""
    assert "30-8-1" in speakable("нарушение NMSA § 30-8-1 о правонарушении")
    # A number that stands on its own is still expanded.
    assert speakable("статья 30 кодекса") == "статья тридцать кодекса"


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


# --- splitting into pieces the model finishes -------------------------------
#
# Every article that came back broken was long. Seven whole articles in one
# generation each produced one usable file; two independent bug reports against
# Qwen3-TTS describe the same shape (speech dropping out of the middle,
# mlx-audio #464; the speaking rate drifting past ~100 characters, QwenLM #239).
# So the size of a piece is a correctness property, not a tuning preference,
# and it is worth holding still.


def _sentences(count: int, word: str = "слово") -> str:
    """A paragraph of `count` sentences, each comfortably under the ceiling.

    Sized so that six sentences clear the floor: a fixture that accidentally
    lands under MIN_CHUNK_CHARS merges into its neighbour and the test reads as
    a bug in the code.
    """
    sentences = [
        f"{word.capitalize()} номер {index} стоит в этом абзаце тут." for index in range(count)
    ]
    assert not sentences or len(" ".join(sentences[:6])) > MIN_CHUNK_CHARS
    return " ".join(sentences)


def test_the_documented_bounds_are_the_actual_bounds():
    """The literals, not the constants. Every other test here compares against
    MAX_CHUNK_CHARS, so widening the constant would keep them all green while
    silently undoing what the measurements bought."""
    assert (MIN_CHUNK_CHARS, MAX_CHUNK_CHARS) == (120, 700)


def test_the_ceiling_holds_on_the_shape_that_broke_it():
    """A real article came out [717, 773, 6]: over the ceiling twice, and a
    six-character piece sent to the model alone. Greedy filling plus a merge
    pass could break both bounds at once, because the merge never re-checked
    the ceiling it was undoing."""
    script = narration_text(
        "Короткий заголовок",
        "Лид. " + "Слово всякое разное тут. " * 30,
        [("Блок", "Текст. " * 100)],
        date="2026-08-07",
    )

    sizes = [len(piece) for piece in chunks(script)]

    assert max(sizes) <= MAX_CHUNK_CHARS, sizes
    assert min(sizes) >= MIN_CHUNK_CHARS, sizes


def test_pieces_come_out_evenly_sized():
    """Not just under the ceiling — near each other. A piece at the ceiling
    next to a piece at the floor is the arrangement that strands a tail."""
    sizes = [len(piece) for piece in chunks(_sentences(200))]
    assert max(sizes) - min(sizes) < MAX_CHUNK_CHARS / 2, sizes


def test_crlf_text_still_splits():
    """Path.write_text emits CRLF on Windows, and splitting on "\\n\\n" turns a
    whole article into one unbreakable block — silently, which is the worst way
    for chunking to fail."""
    text = ("\r\n\r\n".join(_sentences(30, w) for w in ("первый", "второй", "третий")))

    pieces = chunks(text)

    assert len(pieces) > 1
    assert all(len(piece) <= MAX_CHUNK_CHARS for piece in pieces)
    assert "\r" not in " ".join(pieces)


def test_text_that_fits_is_not_split_at_all():
    """Under the ceiling there is nothing to gain by splitting, and every join
    between pieces is a place the voice can change character."""
    text = _sentences(6, "первый") + "\n\n" + _sentences(6, "второй")
    assert len(text) < MAX_CHUNK_CHARS

    pieces = chunks(text)

    assert len(pieces) == 1
    assert pieces[0].startswith("Первый")
    assert pieces[0].endswith("тут.")


def test_a_paragraph_break_never_ends_up_inside_a_sentence():
    text = _sentences(40, "первый") + "\n\n" + _sentences(40, "второй")

    for piece in chunks(text):
        assert piece.endswith("."), piece[-40:]
        assert "тут.Второй" not in piece


def test_a_long_paragraph_is_cut_and_every_piece_fits():
    text = _sentences(200)
    assert len(text) > MAX_CHUNK_CHARS * 3

    pieces = chunks(text)

    assert len(pieces) > 3
    assert all(len(piece) <= MAX_CHUNK_CHARS for piece in pieces)


def test_cuts_land_on_sentence_boundaries():
    """Mid-sentence cuts are audible: the piece ends on a rising intonation."""
    for piece in chunks(_sentences(200))[:-1]:
        assert piece.endswith("."), piece[-40:]


def test_nothing_is_lost_when_a_paragraph_is_split():
    text = _sentences(200)
    assert " ".join(chunks(text)).split() == text.split()


def test_nothing_is_lost_across_paragraphs():
    text = "\n\n".join(_sentences(30) for _ in range(4))
    assert " ".join(chunks(text)).split() == text.split()


def test_short_pieces_are_glued_to_the_next_one():
    """Tiny inputs are where the model ran away — nine characters, eleven
    seconds of noise. Nothing short is ever sent on its own."""
    text = "Коротко.\n\n" + _sentences(6)

    pieces = chunks(text)

    assert len(pieces) == 1
    assert pieces[0].startswith("Коротко. ")


def test_only_the_last_piece_may_be_short():
    """A short tail has nothing to merge into; everything before it is full."""
    text = "\n\n".join(["Раз.", "Два.", _sentences(6), "Хвост."])

    pieces = chunks(text)

    assert all(len(piece) >= MIN_CHUNK_CHARS for piece in pieces[:-1])


def test_a_paragraph_without_sentence_breaks_is_not_cut_mid_word():
    """Better one over-long piece than a word sliced in half."""
    text = "слово " * 400

    pieces = chunks(text)

    assert len(pieces) == 1
    assert pieces[0].split() == text.split()


def test_blank_input_produces_no_pieces():
    assert chunks("") == []
    assert chunks("\n\n   \n\n") == []


def test_a_real_narration_splits_into_speakable_pieces():
    """The end-to-end shape: what narration_text produces is what gets spoken."""
    script = narration_text(
        "Заголовок материала",
        _sentences(8, "лид"),
        [("Контекст", _sentences(40)), ("Детали", _sentences(40))],
        date="2026-08-07",
    )

    pieces = chunks(script)

    assert len(pieces) > 2
    assert all(len(piece) <= MAX_CHUNK_CHARS for piece in pieces)
    assert all(piece.strip() for piece in pieces)
    assert " ".join(pieces).split() == script.split()


# --- grading what came back -------------------------------------------------


def test_coverage_is_one_when_everything_was_spoken():
    assert coverage("Раз два три.", "раз, два три!") == 1.0


def test_coverage_ignores_case_and_punctuation():
    assert coverage("Раз, два!", "РАЗ ДВА") == 1.0


def test_coverage_falls_when_words_go_missing():
    assert coverage("раз два три четыре", "раз два") == 0.5


def test_coverage_counts_repeats_separately():
    """A multiset, not a set: saying "раз" once does not cover it twice."""
    assert coverage("раз раз два два", "раз два") == 0.5


def test_coverage_is_recall_not_precision():
    """Extra words a recogniser invented are not the failure being hunted."""
    assert coverage("раз два", "раз два три четыре пять") == 1.0


def test_spelling_of_yo_does_not_cost_points():
    """Russian writes ё and е for the same sound and transcribers pick freely.
    "остаётся" came back as "остается" and cost real points — the measurement
    being wrong about the audio, not the audio being wrong."""
    assert coverage("остаётся непроверенным", "остается непроверенным") == 1.0
    assert reached_the_end(
        "текст остаётся непроверенным", "текст остается непроверенным"
    ) == 1.0


def test_coverage_of_nothing_is_one():
    assert coverage("", "что-то") == 1.0
    assert coverage("   ", "") == 1.0


def test_reached_the_end_is_one_for_a_complete_reading():
    source = _sentences(20)
    assert reached_the_end(source, source) == 1.0


def test_reached_the_end_collapses_when_the_reading_breaks_off():
    """The real failure: it stops early and fills the rest with noise."""
    source = _sentences(20) + " Заключительная мысль этого текста целиком."
    heard = _sentences(10) + " Продолжение следует."

    assert reached_the_end(source, heard) < 0.5


def test_reached_the_end_survives_a_misheard_word_in_the_middle():
    """Whole-text coverage never cleared a threshold truncation would fail —
    a recogniser mishears, and that cost more than truncation did. Looking at
    the end only is what made the check usable."""
    source = _sentences(20)
    heard = source.replace("номер 3 ", "намер 3 ").replace("номер 7 ", "намер 7 ")

    assert coverage(source, heard) < 1.0
    assert reached_the_end(source, heard) == 1.0


def test_reached_the_end_finds_the_tail_anywhere_in_the_transcript():
    """Position is not the signal — presence is. A recogniser that dropped a
    sentence mid-way still proves it read to the end."""
    source = "начало середина хвост этого текста"
    assert reached_the_end(source, "хвост этого текста начало середина") == 1.0


def test_reached_the_end_ignores_tail_words_that_occur_earlier_too():
    """The words that prove the end was reached are the ones found only there.

    Scoring every tail word let filler carry the check: an ending made of
    ordinary words scored a truncated reading 0.5, because those same words sat
    all over the part the model *did* read.
    """
    source = "тут и там. " * 20 + "финальная реплика."
    heard = "тут и там. " * 8

    assert reached_the_end(source, heard) == 0.0


def test_reached_the_end_handles_a_source_shorter_than_the_window():
    assert reached_the_end("раз два", "раз два") == 1.0
    assert reached_the_end("раз два", "") == 0.0


def test_reached_the_end_of_nothing_is_one():
    assert reached_the_end("", "") == 1.0


# --- finding where the speech actually stops --------------------------------


def _segment(start: float, end: float, text: str) -> dict:
    return {"start": start, "end": end, "text": text}


def test_speech_ends_at_the_last_real_segment():
    segments = [
        _segment(0.0, 4.0, "Первая фраза этой записи звучит целиком."),
        _segment(4.0, 9.0, "Вторая фраза этой записи тоже звучит целиком."),
    ]
    assert speech_ends_at(segments) == 9.0


def test_a_hallucinated_tail_does_not_count_as_speech():
    """The exact failure: it stopped at 9s and padded 20s with babble."""
    segments = [
        _segment(0.0, 9.0, "Настоящая речь, произнесённая полностью и разборчиво."),
        _segment(9.0, 29.0, "Продолжение следует."),
    ]
    assert speech_ends_at(segments) == 9.0


def test_a_recording_with_no_speech_at_all_ends_at_zero():
    assert speech_ends_at([_segment(0.0, 30.0, "...")]) == 0.0
    assert speech_ends_at([]) == 0.0


def test_a_zero_length_segment_does_not_divide_by_zero():
    assert speech_ends_at([_segment(3.0, 3.0, "Раз.")]) == 3.0


def test_speech_after_a_gap_still_counts():
    """A pause mid-recording is not the end — only the last real speech is."""
    segments = [
        _segment(0.0, 4.0, "Первая фраза этой записи звучит целиком."),
        _segment(4.0, 12.0, " "),
        _segment(12.0, 17.0, "Последняя фраза этой записи тоже звучит целиком."),
    ]
    assert speech_ends_at(segments) == 17.0


# --- putting the player on the page -----------------------------------------

PAGE = (
    "# Заголовок\n\n"
    '<p class="hz-byline">Источник · 7 августа</p>\n\n'
    "Текст статьи.\n"
)


def test_the_player_lands_under_the_byline():
    result = attach_player(PAGE, "https://audio.example/a.opus", 213)

    assert "</p>\n\n<audio" in result
    assert result.index("hz-narration") > result.index("hz-byline")
    assert result.index("hz-narration") < result.index("Текст статьи.")
    assert 'src="https://audio.example/a.opus"' in result


def test_re_narrating_replaces_the_player_instead_of_stacking_them():
    once = attach_player(PAGE, "https://audio.example/old.opus", 213)
    twice = attach_player(once, "https://audio.example/new.opus", 240)

    assert twice.count("hz-narration") == 1
    assert "old.opus" not in twice
    assert "new.opus" in twice


def test_re_narrating_is_stable():
    """Same audio twice must give byte-identical markup, or every re-run shows
    up as a diff in the published page."""
    once = attach_player(PAGE, "https://audio.example/a.opus", 213)
    assert attach_player(once, "https://audio.example/a.opus", 213) == once


def test_the_duration_is_announced_in_whole_minutes():
    assert 'aria-label="Озвучка статьи, 4 мин"' in attach_player(PAGE, "u", 213)
    # Never "0 мин": a short piece still takes time to listen to.
    assert 'aria-label="Озвучка статьи, 1 мин"' in attach_player(PAGE, "u", 9)


def test_a_page_without_a_byline_is_refused_not_silently_skipped():
    with pytest.raises(ValueError):
        attach_player("# Заголовок\n\nТекст.\n", "u", 60)


def test_the_rest_of_the_page_is_untouched():
    result = attach_player(PAGE, "u", 60)
    assert result.startswith("# Заголовок\n\n")
    assert result.endswith("Текст статьи.\n")


# --- the address the audio is published at ----------------------------------


def test_new_audio_gets_a_new_address():
    """What makes `immutable` caching honest. Overwriting one address left every
    cache, browser and edge, serving the old take forever."""
    assert audio_key("2026-08-07-ru", "tech-news-2", b"first") != audio_key(
        "2026-08-07-ru", "tech-news-2", b"second"
    )


def test_the_same_audio_keeps_its_address():
    """Re-uploading an unchanged file must not churn the URL on the page."""
    assert audio_key("2026-08-07-ru", "tech-news-2", b"same") == audio_key(
        "2026-08-07-ru", "tech-news-2", b"same"
    )


def test_the_key_is_grouped_by_issue_and_named_for_the_article():
    key = audio_key("2026-08-07-ru", "tech-news-2", b"x")
    assert key.startswith("2026-08-07-ru/tech-news-2-")
    assert key.endswith(".opus")
