import json

import pytest

from chat_pipeline import messages, service

from .chat_helpers import fake_search


def _refusal(query):
    with fake_search() as search_mock:
        response = service.process_query(query)
    search_mock.assert_not_called()
    return response


def test_ac1_a_tamil_trigger_returns_the_tamil_refusal_with_type_refusal():
    response = _refusal("பாராசிட்டமால் டோஸ் என்ன")
    assert response["type"] == "REFUSAL" and response["language"] == "TA" and response["success"] is True
    assert response["message"] == messages.get_message("refusal", "TA")
    assert any("\u0b80" <= ch <= "\u0bff" for ch in response["message"])


def test_ac2_an_english_trigger_returns_the_english_refusal():
    response = _refusal("what dose of paracetamol should I take")
    assert response["language"] == "EN" and response["message"] == messages.get_message("refusal", "EN")
    assert not any("\u0b80" <= ch <= "\u0bff" for ch in response["message"])


def test_ac2_romanised_tamil_is_undetermined_so_the_english_refusal_is_returned_not_tamil():
    response = _refusal("enakku dengue irukkumaa")
    assert response["type"] == "REFUSAL" and response["language"] == "EN"
    assert response["message"] == messages.get_message("refusal", "EN")


@pytest.mark.parametrize("language", ["EN", "UNKNOWN", None, "xx"])
def test_ac2_anything_that_is_not_ta_gets_english(language):
    assert messages.get_message("refusal", language) == messages.get_message("refusal", "EN")


def test_ac3_the_refusal_is_static_text_from_the_resource_files_and_offers_help(monkeypatch):
    called = []
    monkeypatch.setattr("chat_pipeline.service.get_generator", lambda: called.append("llm"))
    response = _refusal("can you prescribe me an antibiotic")
    assert called == []                                             # no LLM, so no generated content
    en = json.loads((messages.RESOURCE_DIR / "messages_en.json").read_text(encoding="utf-8"))
    assert response["message"] == en["refusal"]
    assert "consult a doctor" in en["refusal"].lower() and "approved topics" in en["refusal"].lower()


def test_both_languages_have_a_refusal_and_it_differs_from_the_fallback():
    for language in ("EN", "TA"):
        assert messages.get_message("refusal", language) != messages.get_message("fallback", language)


def test_the_two_resource_files_have_the_same_keys():
    en = json.loads((messages.RESOURCE_DIR / "messages_en.json").read_text(encoding="utf-8"))
    ta = json.loads((messages.RESOURCE_DIR / "messages_ta.json").read_text(encoding="utf-8"))
    assert set(en) == set(ta) and set(en["days"]) == set(ta["days"])