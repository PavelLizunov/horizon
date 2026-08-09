"""Latin words, said the way a Russian narrator says them.

Measured need: 13.5% of the words in a digest are Latin — 818 of 6067 across
466 distinct tokens. Silero's Russian model has no Latin graphemes and drops
them silently, so "device plugin в Kubernetes" is spoken as "в".
"""

from src.ai.narration import speakable
from src.ai.translit import cyrillic, has_latin


def test_known_names_are_said_the_way_people_say_them():
    """No rule derives "кубернетес" from "Kubernetes"; a list does."""
    assert cyrillic("в Kubernetes") == "в кубернетес"
    assert cyrillic("OpenAI и Anthropic") == "оупен-эй-ай и антропик"


def test_acronyms_are_read_letter_by_letter():
    assert cyrillic("целые GPU") == "целые джи-пи-ю"
    assert cyrillic("в GA") == "в джи-эй"


def test_a_capitalised_name_is_not_mistaken_for_an_acronym():
    """"Sol" and "Luna" are names; only short all-caps runs get spelled out."""
    assert "-" not in cyrillic("Sol")


def test_unknown_words_are_transliterated_rather_than_dropped():
    """An approximation that is spoken beats a word silently missing."""
    spoken = cyrillic("consumable capacity")
    assert not has_latin(spoken)
    assert spoken == "консумабл капакити"


def test_a_name_with_digits_is_letters_and_a_number_in_turn():
    assert cyrillic("MI300X") == "эм-ай триста кс"
    assert cyrillic("GPT-4o") == "джи-пи-ти-четыре о"


def test_plain_numbers_are_left_for_the_number_rules():
    """narration.py knows about units and dates; this module must not touch
    them or it would expand "15" without its "процентов"."""
    assert cyrillic("выросла на 15 процентов") == "выросла на 15 процентов"
    assert cyrillic("2026 года") == "2026 года"


def test_nothing_latin_survives_a_real_sentence():
    source = "device plugin в Kubernetes умел лишь считать целые GPU, поэтому HAMi построил"
    assert not has_latin(cyrillic(source))


def test_it_runs_after_the_numbers_not_before():
    """speakable() first, then this: the other order transliterates the "v" of
    "v1.36" and leaves ".36" behind as digits."""
    assert cyrillic(speakable("Kubernetes v1.36 вышел")) == (
        "кубернетес в один точка тридцать шесть вышел"
    )


def test_has_latin():
    assert has_latin("в Kubernetes")
    assert not has_latin("в кубернетес")
