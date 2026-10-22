from unittest import mock

import pytest

from chat_pipeline import fixed_answers, service


@pytest.mark.parametrize(('query', 'intent', 'language'), [
    ('What are the clinic hours?', 'hours', 'EN'),
    ('When does OneCare open?', 'hours', 'EN'),
    ('What time does the clinic close?', 'hours', 'EN'),
    ('Clinic opening time?', 'hours', 'EN'),
    ('கிளினிக் நேரம் என்ன?', 'hours', 'TA'),
    ('Is the doctor available today?', 'doctors', 'EN'),
    ('What time is the doctor available?', 'doctors', 'EN'),
    ('Can I see a doctor today?', 'doctors', 'EN'),
    ('இன்று மருத்துவர் இருக்கிறாரா?', 'doctors', 'TA'),
    ('How can I book an appointment?', 'booking', 'EN'),
    ('How do I make a doctor appointment?', 'booking', 'EN'),
    ('Where can I book an appointment?', 'booking', 'EN'),
    ('அப்பாயிண்ட்மென்ட் எப்படி பதிவு செய்வது?', 'booking', 'TA'),
    ('What services does OneCare provide?', 'services', 'EN'),
    ('What are your services?', 'services', 'EN'),
    ('What services are available?', 'services', 'EN'),
    ('கிளினிக்கில் என்னென்ன சேவைகள் உள்ளன?', 'services', 'TA'),
])
def test_fixed_answers_after_guardrails(query, intent, language, settings):
    settings.CHAT_FIXED_CLINIC_ENABLED = True
    with mock.patch('chat_pipeline.service.search.similarity_search') as search:
        response = service.process_query(query)
    assert response['type'] == 'CLINIC_FACT'
    assert response['language'] == language
    assert response['clinicInfoSource'] == 'CONFIGURED'
    search.assert_not_called()
    if intent in ('hours', 'doctors'):
        assert '5:00' in response['message'] and '11:00' in response['message']
    if intent == 'booking':
        assert response['action'] == {'type': 'BOOK_APPOINTMENT'}
    if intent == 'services':
        assert len(response['message'].splitlines()) == 8


@pytest.mark.parametrize('query', [
    'What are City Hospital clinic hours?', 'What services does another clinic offer?',
    'Is Dr Silva available today?', 'Is the doctor available tomorrow?',
    'healthy eating tips for diabetes', 'clinic hours and prescribe me antibiotics',
])
def test_no_broad_keyword_matches(query):
    assert fixed_answers.detect_intent(query) is None


def test_safety_precedes_fixed_answers(settings):
    settings.CHAT_FIXED_CLINIC_ENABLED = True
    with mock.patch('chat_pipeline.service.fixed_answers.answer') as answer:
        assert service.process_query('clinic hours and what medicine should I take')['type'] == 'REFUSAL'
    answer.assert_not_called()


def test_live_mode_remains_available(settings):
    settings.CHAT_FIXED_CLINIC_ENABLED = False
    assert fixed_answers.answer('clinic hours', 'EN') is None
