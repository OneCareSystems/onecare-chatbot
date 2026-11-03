"""UI-02: the suggested-question chips must steer patients INTO scope.
Reads qa/data/chips.json (written by `npm run export-chips` in the frontend folder).
  - no chip may be refused by the guardrail (that would defeat the purpose of the chips)
  - the hours and doctor chips must reach the clinic-fact router, in both languages
  - a chip's language must be detected as its own language"""
import json
from pathlib import Path
from unittest import mock

import pytest

from chat_pipeline import clinic, guardrail, service
from knowledgebase.language import detect_query_language

from .chat_helpers import fake_search, hit

CHIPS_FILE = Path(__file__).resolve().parents[1] / "qa" / "data" / "chips.json"
CHIPS = json.loads(CHIPS_FILE.read_text(encoding="utf-8"))
ALL = [pytest.param(lang, chip, id=f"{lang}-{chip['id']}") for lang in ("en", "ta") for chip in CHIPS[lang]]
HOURS_JSON = {"success": True, "data": {"days": [{"day": "MONDAY", "open": "09:00", "close": "17:00", "closed": False}]}}
DOCTORS_JSON = {"success": True, "data": {"doctors": [{"name": "Dr Perera", "availableSlots": 4}]}}


def _http(body):
    r = mock.Mock()
    r.status_code = 200
    r.json.return_value = body
    return r


def test_both_languages_have_the_same_chip_ids():
    assert [c["id"] for c in CHIPS["en"]] == [c["id"] for c in CHIPS["ta"]]
    assert len(CHIPS["en"]) >= 3


@pytest.mark.parametrize("lang,chip", ALL)
def test_no_chip_is_blocked_by_the_guardrail(lang, chip):
    decision = guardrail.evaluate(chip["query"])
    assert decision.blocked is False, f"{chip['query']!r} would be refused ({decision.category})"


@pytest.mark.parametrize("lang,chip", ALL)
def test_a_chip_is_detected_as_its_own_language(lang, chip):
    assert detect_query_language(chip["query"]).language == lang.upper()


@pytest.mark.parametrize("lang", ["en", "ta"])
def test_the_hours_chip_reaches_the_clinic_hours_router(lang):
    chip = next(c for c in CHIPS[lang] if c["id"] == "hours")
    assert clinic.detect_clinic_intent(chip["query"]) == clinic.HOURS


@pytest.mark.parametrize("lang", ["en", "ta"])
def test_the_doctor_chip_reaches_the_availability_router(lang):
    chip = next(c for c in CHIPS[lang] if c["id"] == "doctors")
    assert clinic.detect_clinic_intent(chip["query"]) == clinic.AVAILABILITY


@pytest.mark.parametrize("lang", ["en", "ta"])
def test_clinic_chips_give_a_live_answer_end_to_end(lang):
    for chip_id, body in (("hours", HOURS_JSON), ("doctors", DOCTORS_JSON)):
        chip = next(c for c in CHIPS[lang] if c["id"] == chip_id)
        with mock.patch("chat_pipeline.clinic.requests.get", return_value=_http(body)), fake_search([hit(0.99)]) as kb:
            response = service.process_query(chip["query"])
        assert response["type"] == "CLINIC_FACT" and response["language"] == lang.upper()
        kb.assert_not_called()                      # live data comes from Spring, never from the knowledge base


@pytest.mark.parametrize("lang,chip", ALL)
def test_no_chip_ever_gets_a_refusal_from_the_pipeline(lang, chip):
    with mock.patch("chat_pipeline.clinic.requests.get", return_value=_http(HOURS_JSON)), fake_search([hit(0.2)]):
        assert service.process_query(chip["query"])["type"] != "REFUSAL"