from unittest import mock

import pytest

from chat_pipeline.llm import GroqClient, LLMUnavailable, get_llm_client


@pytest.fixture
def groq(settings):
    settings.LLM_PROVIDER = "groq"
    settings.LLM_MODEL = "openai/gpt-oss-120b"
    settings.LLM_MAX_TOKENS = 2048
    settings.LLM_REASONING_EFFORT = "low"
    return get_llm_client()


def response(status=200):
    result = mock.Mock(status_code=status, headers={})
    result.json.return_value = {
        "choices": [{"message": {"content": " Answer. ", "reasoning": "Internal reasoning"}}]
    }
    return result


def test_groq_endpoint_authentication_and_final_answer(groq):
    assert isinstance(groq, GroqClient)
    with mock.patch("chat_pipeline.llm.requests.post", return_value=response()) as post:
        assert groq.complete("SYSTEM", "USER") == "Answer."
    assert post.call_args.args[0] == "https://api.groq.com/openai/v1/chat/completions"
    assert post.call_args.kwargs["headers"]["Authorization"] == "Bearer test-key-123"
    assert post.call_args.kwargs["timeout"] == (1, 1)
    assert post.call_args.kwargs["json"] == {
        "model": "openai/gpt-oss-120b",
        "max_completion_tokens": 2048,
        "include_reasoning": False,
        "reasoning_effort": "low",
        "temperature": 0.0,
        "messages": [
            {"role": "system", "content": "SYSTEM"},
            {"role": "user", "content": "USER"},
        ],
    }


def test_non_oss_models_do_not_receive_oss_option(settings, groq):
    groq.model = "another-groq-model"
    settings.LLM_REASONING_EFFORT = ""
    body = groq._request_body("SYSTEM", "USER")
    assert "include_reasoning" not in body
    assert "reasoning_effort" not in body


def test_groq_honors_custom_base_url(settings, groq):
    settings.LLM_BASE_URL = "https://groq-gateway.test/v1/"
    with mock.patch("chat_pipeline.llm.requests.post", return_value=response()) as post:
        get_llm_client().complete("SYSTEM", "USER")
    assert post.call_args.args[0] == "https://groq-gateway.test/v1/chat/completions"


def test_groq_retries_transient_failure(groq):
    with mock.patch("chat_pipeline.llm.requests.post", side_effect=[response(503), response()]) as post:
        assert groq.complete("SYSTEM", "USER") == "Answer."
    assert post.call_count == 2


def test_groq_missing_key_does_not_send_request(groq):
    groq.api_key = ""
    with mock.patch("chat_pipeline.llm.requests.post") as post, pytest.raises(LLMUnavailable):
        groq.complete("SYSTEM", "USER")
    post.assert_not_called()
