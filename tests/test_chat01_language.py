import logging

import pytest

from knowledgebase import language
from knowledgebase.language import detect_query_language


def test_ac1_tamil_script_is_ta():
    assert detect_query_language("கிளினிக் நேரம் என்ன").language == "TA"


def test_ac1_english_is_en():
    result = detect_query_language("what are your opening hours today")
    assert (result.language, result.reason) == ("EN", "LATIN_SCRIPT_DEFAULT_EN")


def test_tamil_with_an_english_drug_name_is_still_ta():
    assert detect_query_language("பாராசிட்டமால் paracetamol எதற்கு பயன்படுகிறது").language == "TA"


@pytest.mark.parametrize("query", ["", "   ", "\n\t", None])
def test_ac2_empty_or_whitespace_defaults_to_en(query, caplog):
    with caplog.at_level(logging.INFO, logger="knowledgebase.language"):
        result = detect_query_language(query)
    assert (result.language, result.reason) == ("EN", "EMPTY_QUERY_DEFAULT_EN")
    assert "reason=EMPTY_QUERY_DEFAULT_EN" in caplog.text            # the decision is logged


def test_ac2_detector_exception_defaults_to_en_and_does_not_crash(monkeypatch, caplog):
    monkeypatch.setattr(language, "script_counts", lambda text: (_ for _ in ()).throw(RuntimeError("boom")))
    with caplog.at_level(logging.INFO, logger="knowledgebase.language"):
        result = detect_query_language("hello there friend")
    assert (result.language, result.reason) == ("EN", "DETECTOR_ERROR_DEFAULT_EN")
    assert "DETECTOR_ERROR_DEFAULT_EN" in caplog.text


@pytest.mark.parametrize("query", ["hours", "doctor available", "நேரம்?".replace("நேரம்", "ok")])
def test_ac3_ambiguous_short_latin_query_defaults_to_en(query):
    assert detect_query_language(query).language == "EN"


def test_ac3_short_latin_reason_is_logged():
    assert detect_query_language("hours").reason == "SHORT_QUERY_DEFAULT_EN"


@pytest.mark.parametrize("query", ["enakku fever irukku doctor irukkaara", "clinic neram enna", "naalai doctor irukkaara"])
def test_ac3_romanised_tamil_defaults_to_en(query):
    result = detect_query_language(query)
    assert (result.language, result.reason) == ("EN", "LATIN_SCRIPT_DEFAULT_EN")


def test_digits_and_symbols_only_default_to_en():
    assert detect_query_language("1234 ???").reason == "NO_LETTERS_DEFAULT_EN"


def test_mixed_input_below_the_threshold_is_en():
    assert detect_query_language("what is this நேரம் about clinic please").language == "EN"


def test_threshold_is_configurable(settings):
    settings.CHAT_TAMIL_SHARE_THRESHOLD = 0.9
    assert detect_query_language("பாராசிட்டமால் paracetamol tablet side effects").language == "EN"


def test_the_query_text_is_never_logged(caplog):
    secret = "my secret query about paracetamol"
    with caplog.at_level(logging.DEBUG):
        detect_query_language(secret)
    assert secret not in caplog.text and "paracetamol" not in caplog.text


def test_the_existing_kb04_detector_is_untouched():
    assert language.detect_language("hello world this is english text") == ("EN", False)