import json
import logging

import pytest

from chat_pipeline import guardrail, patterns, service
from chat_pipeline.errors import PatternConfigError
from knowledgebase.language import detect_query_language

from .chat_data import BENIGN, EN_UNSAFE, ROMANISED_UNSAFE, TA_UNSAFE
from .chat_helpers import fake_search


@pytest.mark.parametrize("query,category", EN_UNSAFE + TA_UNSAFE + ROMANISED_UNSAFE)
def test_ac1_unsafe_queries_trigger_the_guardrail(query, category):
    decision = guardrail.evaluate(query)
    assert decision.blocked and decision.category == category


def test_ac1_the_guardrail_triggers_before_retrieval_or_the_llm(monkeypatch):
    called = []
    monkeypatch.setattr("chat_pipeline.service.get_generator", lambda: called.append("llm"))
    with fake_search() as search_mock:
        response = service.process_query("what dose of paracetamol should I take")
    assert response["type"] == "REFUSAL"
    search_mock.assert_not_called()
    assert called == []


@pytest.mark.parametrize("query", [q for q, _ in TA_UNSAFE])
def test_ac3_tamil_questions_give_the_same_result_as_english(query):
    assert guardrail.evaluate(query).blocked is True


def test_all_pattern_sets_run_whatever_language_chat01_detected():
    query = "enakku dengue irukkumaa"                        # romanised Tamil: CHAT-01 says EN
    assert detect_query_language(query).language == "EN"
    decision = guardrail.evaluate(query)
    assert decision.blocked and decision.pattern_set == "romanised"      # the romanised set still ran


@pytest.mark.parametrize("query", BENIGN)
def test_ac4_informational_questions_are_not_blocked(query):
    assert guardrail.evaluate(query).blocked is False


def test_ac4_what_is_paracetamol_used_for_goes_on_to_retrieval():
    from .chat_helpers import hit
    with fake_search([hit(0.95)]) as search_mock:
        response = service.process_query("what is paracetamol used for")
    assert response["type"] == "ANSWER"
    search_mock.assert_called_once()


def test_ac2_a_classifier_error_is_refused_fail_closed_and_logged(monkeypatch, caplog):
    monkeypatch.setattr(guardrail, "first_match", lambda *a: (_ for _ in ()).throw(RuntimeError("boom")))
    called = []
    monkeypatch.setattr("chat_pipeline.service.get_generator", lambda: called.append("llm"))
    with fake_search() as search_mock, caplog.at_level(logging.ERROR):
        response = service.process_query("what is paracetamol used for")
    assert response["type"] == "REFUSAL"                       # refused, not answered
    search_mock.assert_not_called()
    assert called == []                                        # neither retrieval nor the LLM
    assert "fail-closed" in caplog.text


def test_ac2_a_missing_pattern_file_is_fail_closed(settings, tmp_path):
    settings.CHAT_PATTERNS_FILE = tmp_path / "nope.json"
    patterns.reset_cache()
    decision = guardrail.evaluate("what is paracetamol used for")
    assert decision.blocked and decision.category == "GUARDRAIL_ERROR"


def test_a_broken_regex_in_the_config_is_rejected(settings, tmp_path):
    data = json.loads(patterns.DEFAULT_FILE.read_text(encoding="utf-8"))
    data["pre_generation"]["dosage"]["en"].append("([unclosed")
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(data), encoding="utf-8")
    settings.CHAT_PATTERNS_FILE = bad
    patterns.reset_cache()
    with pytest.raises(PatternConfigError):
        patterns.load_patterns()


def test_an_emptied_pattern_set_is_rejected_not_silently_accepted(settings, tmp_path):
    data = json.loads(patterns.DEFAULT_FILE.read_text(encoding="utf-8"))
    data["pre_generation"]["diagnosis"]["ta"] = []
    bad = tmp_path / "empty.json"
    bad.write_text(json.dumps(data), encoding="utf-8")
    settings.CHAT_PATTERNS_FILE = bad
    patterns.reset_cache()
    assert guardrail.evaluate("what is paracetamol used for").category == "GUARDRAIL_ERROR"


def test_the_shipped_config_is_valid_and_has_all_three_sets():
    loaded = patterns.load_patterns()
    for category in ("dosage", "diagnosis", "prescription"):
        assert set(loaded["pre_generation"][category]) == {"en", "ta", "romanised"}


def test_the_query_text_is_never_logged(caplog):
    with caplog.at_level(logging.DEBUG):
        guardrail.evaluate("what dose of paracetamol should I take")
    assert "paracetamol" not in caplog.text and "category=dosage" in caplog.text