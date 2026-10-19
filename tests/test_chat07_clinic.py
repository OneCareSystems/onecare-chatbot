import importlib.util
import threading
from datetime import date
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

import pytest
import requests

from chat_pipeline import clinic, messages, service
from chat_pipeline.errors import ClinicUnavailable

from .chat_data import AVAILABILITY_QUERIES, HOURS_QUERIES
from .chat_helpers import fake_search, hit
from .helpers import auth

HOURS_JSON = {"success": True, "data": {"days": [
    {"day": "MONDAY", "open": "09:00", "close": "17:00", "closed": False},
    {"day": "SUNDAY", "open": None, "close": None, "closed": True}]}}
DOCTORS_JSON = {"success": True, "data": {"doctors": [
    {"name": "Dr Perera", "availableSlots": 4, "patientName": "MUST NOT APPEAR"},
    {"name": "Dr Silva", "availableSlots": 0}]}}


def _response(status=200, body=None):
    r = mock.Mock()
    r.status_code = status
    r.json.return_value = body
    return r


@pytest.mark.parametrize("query", HOURS_QUERIES)
def test_hours_queries_are_detected_in_en_ta_and_romanised(query):
    assert clinic.detect_clinic_intent(query) == clinic.HOURS


@pytest.mark.parametrize("query", AVAILABILITY_QUERIES)
def test_availability_queries_are_detected(query):
    assert clinic.detect_clinic_intent(query) == clinic.AVAILABILITY


@pytest.mark.parametrize("query", ["what is paracetamol used for", "கிளினிக்கில் என்ன சேவைகள்", "how do I book"])
def test_other_queries_are_not_clinic_facts(query):
    assert clinic.detect_clinic_intent(query) is None


def test_ac1_clinic_hours_come_from_spring_not_the_kb_en_and_ta():
    with mock.patch("chat_pipeline.clinic.requests.get", return_value=_response(200, HOURS_JSON)), fake_search([hit()]) as kb:
        en = service.process_query("clinic hours?")
        ta = service.process_query("கிளினிக் நேரம் என்ன")
    kb.assert_not_called()                                               # the KB is never consulted
    assert en["type"] == ta["type"] == "CLINIC_FACT"
    assert "Monday 09:00-17:00" in en["message"] and "Sunday: closed" in en["message"]
    assert "திங்கள் 09:00-17:00" in ta["message"] and ta["language"] == "TA"


def test_availability_uses_the_requested_date_and_hides_full_doctors_and_patient_data(monkeypatch):
    monkeypatch.setattr(clinic.timezone, "localdate", lambda: date(2026, 10, 17))
    with mock.patch("chat_pipeline.clinic.requests.get", return_value=_response(200, DOCTORS_JSON)) as get:
        response = service.process_query("is the doctor available tomorrow")
    assert get.call_args.kwargs["params"] == {"date": "2026-10-18"}
    assert "Dr Perera (4 slots)" in response["message"] and "Dr Silva" not in response["message"]
    assert "MUST NOT APPEAR" not in str(response)


def test_a_named_doctor_filters_the_answer(monkeypatch):
    body = {"data": {"doctors": [{"name": "Dr Perera", "availableSlots": 4}, {"name": "Dr Fernando", "availableSlots": 2}]}}
    with mock.patch("chat_pipeline.clinic.requests.get", return_value=_response(200, body)):
        message = service.process_query("is dr fernando available today")["message"]
    assert "Fernando" in message and "Perera" not in message


def test_no_free_doctor_is_a_real_answer_not_a_failure(monkeypatch):
    with mock.patch("chat_pipeline.clinic.requests.get", return_value=_response(200, {"data": {"doctors": []}})):
        response = service.process_query("doctor availability today")
    assert response["type"] == "CLINIC_FACT" and "No doctors" in response["message"]


@pytest.mark.parametrize("failure", [
    {"side_effect": requests.ConnectionError("down")},
    {"side_effect": requests.Timeout("slow")},
    {"return_value": _response(503, {})},
    {"return_value": _response(500, {})},
    {"return_value": _response(200, {"data": {"unexpected": 1}})},
    {"return_value": _response(200, ["not", "an", "object"])},
])
def test_ac2_spring_unavailable_gives_the_localised_fallback_not_a_kb_answer(failure):
    with mock.patch("chat_pipeline.clinic.requests.get", **failure), fake_search([hit(0.99)]) as kb:
        en = service.process_query("clinic hours?")
        ta = service.process_query("கிளினிக் நேரம் என்ன")
    kb.assert_not_called()                                               # no stale KB answer
    assert en["type"] == ta["type"] == "FALLBACK" and en["reason"] == "CLINIC_DATA_UNAVAILABLE"
    assert en["message"] == messages.get_message("fallback", "EN") and ta["message"] == messages.get_message("fallback", "TA")


def test_ac2_invalid_json_from_spring_is_a_fallback():
    bad = _response(200)
    bad.json.side_effect = ValueError("not json")
    with mock.patch("chat_pipeline.clinic.requests.get", return_value=bad):
        assert service.process_query("clinic hours?")["type"] == "FALLBACK"


def test_ac3_a_401_from_spring_gives_the_fallback_never_a_401_to_the_patient(caplog):
    with mock.patch("chat_pipeline.clinic.requests.get", return_value=_response(401, {})):
        response = service.process_query("clinic hours?")
    assert response["success"] is True and response["type"] == "FALLBACK"
    assert "service credential" in caplog.text and "spring-service-token" not in caplog.text


def test_ac3_only_the_service_credential_is_sent_and_the_inbound_jwt_is_never_forwarded(client):
    with mock.patch("chat_pipeline.clinic.requests.get", return_value=_response(200, HOURS_JSON)) as get:
        r = client.post("/internal/chat/query", data='{"query": "clinic hours?"}', content_type="application/json",
                        **auth("42"))                        # inbound: Spring->Django service token + user id header
    assert r.status_code == 200
    headers = get.call_args.kwargs["headers"]
    assert headers == {"Accept": "application/json", "Authorization": "Bearer spring-service-token"}
    assert get.call_args.kwargs["allow_redirects"] is False and get.call_args.kwargs["timeout"] == (1, 1)


def test_ac3_with_no_service_credential_configured_no_authorization_header_is_sent(settings):
    settings.SPRING_SERVICE_TOKEN = ""
    with mock.patch("chat_pipeline.clinic.requests.get", return_value=_response(401, {})) as get:
        assert service.process_query("clinic hours?")["type"] == "FALLBACK"
    assert "Authorization" not in get.call_args.kwargs["headers"]


def test_no_base_url_is_a_typed_error(settings):
    settings.SPRING_BASE_URL = ""
    with pytest.raises(ClinicUnavailable):
        clinic.SpringClinicClient().get_hours()


def test_there_is_exactly_one_attempt_no_retry_storm():
    with mock.patch("chat_pipeline.clinic.requests.get", side_effect=requests.Timeout("slow")) as get:
        service.process_query("clinic hours?")
    assert get.call_count == 1


# ---------- real HTTP against tools/mock_spring.py ----------
@pytest.fixture
def mock_spring(settings):
    path = Path(__file__).resolve().parents[1] / "tools" / "mock_spring.py"
    spec = importlib.util.spec_from_file_location("mock_spring", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    servers = []

    def start(token="good-token", mode="ok"):
        server = ThreadingHTTPServer(("127.0.0.1", 0), module.make_handler(token, mode))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
        settings.SPRING_BASE_URL = f"http://127.0.0.1:{server.server_address[1]}"
        return server
    yield start
    for server in servers:
        server.shutdown()


def test_real_http_good_credential_returns_live_hours(mock_spring, settings):
    mock_spring()
    settings.SPRING_SERVICE_TOKEN = "good-token"
    response = service.process_query("clinic hours?")
    assert response["type"] == "CLINIC_FACT" and "Saturday 09:00-13:00" in response["message"]


def test_real_http_wrong_credential_is_401_and_the_patient_sees_the_fallback(mock_spring, settings):
    mock_spring()
    settings.SPRING_SERVICE_TOKEN = "wrong-token"
    assert service.process_query("clinic hours?")["type"] == "FALLBACK"


def test_real_http_spring_down_is_the_fallback(mock_spring, settings):
    mock_spring(mode="down")
    settings.SPRING_SERVICE_TOKEN = "good-token"
    assert service.process_query("clinic hours?")["reason"] == "CLINIC_DATA_UNAVAILABLE"


def test_real_http_nothing_listening_is_the_fallback(settings):
    settings.SPRING_BASE_URL = "http://127.0.0.1:9"                      # closed port
    assert service.process_query("clinic hours?")["type"] == "FALLBACK"


def test_bad_data_or_an_unexpected_error_from_spring_still_gives_the_fallback():
    bad_slots = {"data": {"doctors": [{"name": "Dr Perera", "availableSlots": "many"}]}}
    with mock.patch("chat_pipeline.clinic.requests.get", return_value=_response(200, bad_slots)):
        assert service.process_query("doctor availability today")["type"] == "FALLBACK"
    with mock.patch("chat_pipeline.clinic.requests.get", side_effect=RuntimeError("bug")):
        assert service.process_query("clinic hours?")["type"] == "FALLBACK"