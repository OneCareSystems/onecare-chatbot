import io
import logging
from datetime import timedelta
from unittest import mock

import pytest
from django.core.management import call_command
from django.utils import timezone

from chat_pipeline import chat_log, prompts, service
from chat_pipeline.errors import VectorStoreUnavailable
from chat_pipeline.generation import LLMGenerator
from chat_pipeline.models import ChatLog

from .chat_helpers import fake_search, hit

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def logging_on(settings):
    settings.CHAT_LOG_ENABLED = True


class _Client:
    model = "m-1"

    def __init__(self, reply="Paracetamol relieves pain and fever."):
        self.reply = reply

    def complete(self, system, user):
        return self.reply


@pytest.fixture
def llm_reply(monkeypatch):
    def _set(reply):
        monkeypatch.setattr(service, "get_generator", lambda: LLMGenerator(_Client(reply)))
    _set("Paracetamol relieves pain and fever.")
    return _set


def last():
    return ChatLog.objects.latest("created_at")


def test_ac_an_answer_is_logged_with_language_chunks_model_and_no_fallback_path(llm_reply):
    with fake_search([hit(0.93, document_id=7, source="guide.pdf"), hit(0.40, document_id=8, source="other.pdf")]):
        response = service.process_query("what is paracetamol used for")
    row = last()
    assert row.request_id == response["requestId"]
    assert (row.query_text, row.response_text) == ("what is paracetamol used for", response["message"])
    assert (row.response_type, row.detected_language, row.fallback_path) == ("ANSWER", "EN", None)
    assert row.language_reason == "LATIN_SCRIPT_DEFAULT_EN" and row.best_score == 0.93
    assert [(c["documentId"], c["source"], c["score"], c["used"]) for c in row.matched_chunks] == [(7, "guide.pdf", 0.93, True), (8, "other.pdf", 0.4, False)]
    assert row.llm_model == "m-1" and row.prompt_version == prompts.PROMPT_VERSION and row.latency_ms >= 0
    assert all("text" not in c for c in row.matched_chunks)                  # chunk text is never copied into the log


def test_a_tamil_query_is_logged_as_ta(llm_reply):
    llm_reply("பாராசிட்டமால் வலி மற்றும் காய்ச்சலைக் குறைக்கப் பயன்படும் மருந்து.")
    with fake_search([hit(0.9)]):
        service.process_query("பாராசிட்டமால் எதற்கு பயன்படுகிறது")
    assert (last().detected_language, last().language_reason, last().response_type) == ("TA", "TAMIL_SCRIPT", "ANSWER")


def test_a_guardrail_refusal_is_logged_with_its_category_and_no_search():
    with fake_search() as kb:
        service.process_query("what dose of paracetamol should I take")
    kb.assert_not_called()
    row = last()
    assert (row.response_type, row.fallback_path, row.guardrail_category, row.matched_chunks) == ("REFUSAL", "GUARDRAIL_REFUSAL", "dosage", [])


def test_a_guardrail_classifier_error_is_logged_distinctly(monkeypatch):
    monkeypatch.setattr("chat_pipeline.guardrail.first_match", lambda *a: (_ for _ in ()).throw(RuntimeError("x")))
    service.process_query("what is paracetamol used for")
    assert (last().fallback_path, last().guardrail_category) == ("GUARDRAIL_ERROR", "GUARDRAIL_ERROR")


@pytest.mark.parametrize("hits,error,reply,expected_path", [
    ([hit(0.2)], None, None, "NO_CONFIDENT_MATCH"),
    ([], None, None, "NO_CONFIDENT_MATCH"),
    (None, VectorStoreUnavailable("down"), None, "SEARCH_UNAVAILABLE"),
    ([hit(0.95)], None, "NO_ANSWER", "MODEL_NO_ANSWER"),
    ([hit(0.95)], None, "Take 500 mg every 6 hours.", "OUTPUT_BLOCKED"),
    ([hit(0.95)], None, "Wrong language answer", "LANGUAGE_MISMATCH"),
])
def test_every_fallback_path_is_logged(monkeypatch, hits, error, reply, expected_path):
    if reply is not None:
        monkeypatch.setattr(service, "get_generator", lambda: LLMGenerator(_Client(reply)))
    query = "பாராசிட்டமால் எதற்கு பயன்படுகிறது" if expected_path == "LANGUAGE_MISMATCH" else "what is paracetamol used for"
    with fake_search(hits, error=error):
        service.process_query(query)
    assert (last().response_type, last().fallback_path) == ("FALLBACK", expected_path)


def test_the_best_score_is_logged_for_a_low_confidence_fallback():
    with fake_search([hit(0.55)]):
        service.process_query("does the clinic have a car park")
    assert last().best_score == 0.55 and last().matched_chunks[0]["used"] is False


def test_clinic_facts_are_logged_and_a_spring_failure_is_a_fallback_path():
    with mock.patch("chat_pipeline.clinic.requests.get", side_effect=Exception("down")):
        service.process_query("clinic hours?")
    assert (last().response_type, last().fallback_path) == ("FALLBACK", "CLINIC_DATA_UNAVAILABLE")


def test_phone_email_and_id_numbers_are_redacted_before_storage():
    with fake_search([hit(0.2)]):
        service.process_query("call me on 077 123 4567 or mail a.b@example.com my NIC 912345678V and 199012345678")
    text = last().query_text
    assert "[NUMBER]" in text and "[EMAIL]" in text and text.count("[ID]") == 2
    assert "4567" not in text and "example.com" not in text and "912345678" not in text


def test_redaction_can_be_switched_off(settings):
    settings.CHAT_LOG_REDACT = False
    with fake_search([hit(0.2)]):
        service.process_query("mail a.b@example.com")
    assert "a.b@example.com" in last().query_text


def test_long_text_is_truncated(settings):
    settings.CHAT_LOG_MAX_CHARS = 20
    with fake_search([hit(0.2)]):
        service.process_query("x" * 100)
    assert len(last().query_text) == 20


def test_a_failed_log_write_does_not_stop_the_patient_getting_a_response(caplog):
    with mock.patch.object(ChatLog.objects, "create", side_effect=RuntimeError("db down")), fake_search([hit(0.2)]), \
            caplog.at_level(logging.ERROR):
        response = service.process_query("does the clinic have a car park")
    assert response["type"] == "FALLBACK" and "Chat log write failed" in caplog.text


def test_logging_can_be_switched_off(settings):
    settings.CHAT_LOG_ENABLED = False
    with fake_search([hit(0.2)]):
        service.process_query("does the clinic have a car park")
    assert ChatLog.objects.count() == 0


def test_every_request_gets_its_own_unique_request_id():
    with fake_search([hit(0.2)]):
        ids = {service.process_query("does the clinic have a car park")["requestId"] for _ in range(5)}
    assert len(ids) == 5 and ChatLog.objects.count() == 5


def test_the_application_log_still_never_contains_the_query_text(caplog):
    with caplog.at_level(logging.DEBUG), fake_search([hit(0.2)]):
        service.process_query("my private question about paracetamol")
    assert "private question" not in caplog.text


# ---------------- retention and reporting commands ----------------
def _row(days_old, **kw):
    row = ChatLog.objects.create(request_id=f"r{days_old}{kw.get('n', 0)}", query_text="q", response_text="a",
                                 response_type=kw.get("t", "ANSWER"), detected_language="EN", fallback_path=kw.get("p"), latency_ms=100)
    ChatLog.objects.filter(pk=row.pk).update(created_at=timezone.now() - timedelta(days=days_old))


def test_purge_deletes_only_rows_older_than_the_retention_period(settings):
    settings.CHAT_LOG_RETENTION_DAYS = 90
    _row(10), _row(89), _row(91), _row(400)
    out = io.StringIO()
    call_command("purge_chat_logs", "--dry-run", stdout=out)
    assert ChatLog.objects.count() == 4 and "would delete 2" in out.getvalue()
    call_command("purge_chat_logs", stdout=out)
    assert sorted(ChatLog.objects.values_list("request_id", flat=True)) == ["r100", "r890"]
    call_command("purge_chat_logs", "--days", "5", stdout=out)
    assert ChatLog.objects.count() == 0


def test_the_report_counts_by_type_fallback_path_and_language():
    _row(1, t="ANSWER", n=1), _row(1, t="FALLBACK", p="NO_CONFIDENT_MATCH", n=2), _row(1, t="FALLBACK", p="NO_CONFIDENT_MATCH", n=3), _row(30)
    out = io.StringIO()
    call_command("chat_log_report", "--days", "7", stdout=out)
    text = out.getvalue()
    assert "3 queries" in text and "NO_CONFIDENT_MATCH: 2" in text and "ANSWER: 1" in text and "EN: 3" in text


def test_redact_function_directly():
    assert chat_log.redact("NIC 912345678v, +94 77 123 4567, me@x.lk") == "NIC [ID], [NUMBER], [EMAIL]"
    assert chat_log.redact(None) == ""