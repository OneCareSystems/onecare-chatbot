
from chat_pipeline import confidence, messages, service

from .chat_helpers import fake_search, hit


def test_ac1_best_score_below_the_threshold_returns_the_fallback_not_a_refusal():
    with fake_search([hit(0.79)]):
        response = service.process_query("what services does the clinic offer for kids")
    assert response["type"] == "FALLBACK" and response["message"] == messages.get_message("fallback", "EN")
    assert response["message"] != messages.get_message("refusal", "EN")


def test_ac1_the_fallback_is_in_the_query_language():
    with fake_search([hit(0.10, language="EN")]):
        response = service.process_query("உங்கள் கிளினிக்கில் என்னென்ன சேவைகள் உள்ளன")
    assert response["type"] == "FALLBACK" and response["language"] == "TA"
    assert response["message"] == messages.get_message("fallback", "TA")


def test_ac2_no_chunks_at_all_gives_the_fallback_not_an_error():
    with fake_search([]):
        response = service.process_query("what is the clinic parking policy")
    assert response["success"] is True and response["type"] == "FALLBACK" and response["reason"] == "NO_CONFIDENT_MATCH"


def test_ac3_a_score_exactly_at_the_threshold_is_a_match_inclusive():
    assert confidence.is_confident([hit(0.80)], "EN") is True
    assert confidence.is_confident([hit(0.7999)], "EN") is False
    with fake_search([hit(0.80)]):
        assert service.process_query("what is paracetamol used for")["type"] == "ANSWER"


def test_float32_noise_does_not_flip_the_inclusive_rule():
    assert confidence.is_confident([hit(0.79999995)], "EN") is True          # equals 0.8 at 4 decimals


def test_thresholds_are_per_language(settings):
    settings.CHAT_SCORE_THRESHOLDS = {"EN": 0.80, "TA": 0.60, "DEFAULT": 0.80}
    assert confidence.is_confident([hit(0.65)], "TA") is True
    assert confidence.is_confident([hit(0.65)], "EN") is False
    assert confidence.is_confident([hit(0.65)], "UNKNOWN") is False


def test_the_best_hit_decides_not_the_first():
    assert confidence.is_confident([hit(0.5), hit(0.9)], "EN") is True


def test_ac4_a_diagnosis_question_gets_the_refusal_not_the_fallback():
    with fake_search([]) as search_mock:
        response = service.process_query("do I have diabetes")
    assert response["type"] == "REFUSAL"
    search_mock.assert_not_called()