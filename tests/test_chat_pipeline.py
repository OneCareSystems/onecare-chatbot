"""DDP-#37 roll-up: AC1, AC2, AC3 through the whole pipeline, plus the HTTP view Spring Boot will call."""
import json
from unittest import mock

import pytest

from chat_pipeline import messages, service
from chat_pipeline.errors import VectorStoreUnavailable

from .chat_helpers import fake_search, hit
from .helpers import auth

URL = "/internal/chat/query"


def post(client, body, **headers):
    return client.post(URL, data=json.dumps(body) if not isinstance(body, str) else body,
                       content_type="application/json", **(headers or auth(None)))


def test_ac1_an_in_scope_question_in_english_retrieves_a_relevant_answer():
    with fake_search([hit(0.93, document_id=7, source="guide.pdf")]):
        response = service.process_query("what is paracetamol used for")
    assert response["type"] == "ANSWER" and response["language"] == "EN" and response["success"] is True
    assert response["sources"] == [{"documentId": 7, "source": "guide.pdf", "language": "EN", "score": 0.93}]


def test_ac1_an_in_scope_question_in_tamil_retrieves_a_relevant_english_source():
    with fake_search([hit(0.81, language="EN")]):                         # cross-lingual hit, TA threshold 0.75
        response = service.process_query("பாராசிட்டமால் எதற்கு பயன்படுகிறது")
    assert response["type"] == "ANSWER" and response["language"] == "TA"


def test_ac2_a_diagnosis_or_dosage_request_is_refused_before_retrieval_or_generation(monkeypatch):
    llm = []
    monkeypatch.setattr("chat_pipeline.service.get_generator", lambda: llm.append(1))
    with fake_search([hit()]) as kb, mock.patch("chat_pipeline.clinic.requests.get") as spring:
        for query in ("what dose of paracetamol should I take", "எனக்கு டெங்கு இருக்கிறதா", "enakku dengue irukkumaa"):
            assert service.process_query(query)["type"] == "REFUSAL"
    kb.assert_not_called(); spring.assert_not_called()
    assert llm == []


def test_ac3_an_out_of_kb_question_is_a_fallback_not_a_refusal():
    with fake_search([hit(0.12)]):
        response = service.process_query("does the clinic have a car park")
    assert response["type"] == "FALLBACK" and response["message"] == messages.get_message("fallback", "EN")


def test_every_failure_path_returns_a_safe_localised_response(monkeypatch):
    with fake_search(error=VectorStoreUnavailable("down")):                # vector store
        r = service.process_query("what is paracetamol used for")
        assert (r["type"], r["reason"], r["message"]) == ("FALLBACK", "SEARCH_UNAVAILABLE", messages.get_message("unavailable", "EN"))
    monkeypatch.setattr("chat_pipeline.service.get_generator", lambda: (_ for _ in ()).throw(RuntimeError("llm down")))
    with fake_search([hit(0.95)]):                                          # generator
        r = service.process_query("what is paracetamol used for")
        assert r["type"] == "FALLBACK" and r["reason"] == "GENERATION_UNAVAILABLE"


def test_a_vector_store_outage_never_says_no_information():
    with fake_search(error=VectorStoreUnavailable("down")):
        r = service.process_query("what is paracetamol used for")
    assert r["message"] != messages.get_message("fallback", "EN")


def test_the_response_contract_always_has_type_and_language():
    with fake_search([hit(0.95)]), mock.patch("chat_pipeline.clinic.requests.get", side_effect=Exception("spring down")):
        for query in ("what is paracetamol used for", "what dose of paracetamol should I take", "கிளினிக் நேரம் என்ன"):
            r = service.process_query(query)
            assert r["type"] in {"ANSWER", "REFUSAL", "FALLBACK", "CLINIC_FACT"} and r["language"] in {"EN", "TA"}


# ---------------- the HTTP view ----------------
def test_view_requires_the_service_token(client):
    assert client.post(URL, data='{"query": "hi"}', content_type="application/json").status_code == 401


def test_view_returns_the_pipeline_result_with_readable_tamil(client):
    with fake_search([hit(0.9)]):
        r = post(client, {"query": "பாராசிட்டமால் எதற்கு பயன்படுகிறது"})
    assert r.status_code == 200 and r.json()["type"] == "ANSWER" and r.json()["language"] == "TA"
    assert b"\\u0b" not in r.content                                        # Tamil is not \u-escaped


def test_view_refusal_is_http_200_not_an_error(client):
    r = post(client, {"query": "what dose of paracetamol should I take"})
    assert r.status_code == 200 and r.json()["type"] == "REFUSAL" and r.json()["success"] is True


@pytest.mark.parametrize("body", ["not json", "[]", {}, {"query": ""}, {"query": "   "}, {"query": 5}, {"query": None}])
def test_view_rejects_bad_input_with_400(client, body):
    r = post(client, body)
    assert r.status_code == 400 and r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_view_trims_whitespace_before_length_validation(client, settings):
    settings.CHAT_MAX_QUERY_CHARS = 5
    r = post(client, {"query": "  hi  "})
    assert r.status_code == 200
    assert r.json()["message"]


def test_view_rejects_a_query_that_is_too_long(client, settings):
    settings.CHAT_MAX_QUERY_CHARS = 20
    assert post(client, {"query": "x" * 21}).status_code == 400
    with fake_search([hit(0.9)]):
        assert post(client, {"query": "x" * 20}).status_code == 200

def test_view_only_accepts_post(client):
    assert client.get(URL, **auth(None)).status_code == 405