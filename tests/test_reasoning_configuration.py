from unittest import mock

from chat_pipeline.llm import OpenAICompatibleClient
from chat_pipeline.llm import GroqClient, get_llm_client


def test_groq_provider_uses_compatible_endpoint_and_dedicated_key(settings):
    settings.LLM_PROVIDER = 'groq'
    settings.LLM_BASE_URL = ''
    settings.GROQ_API_KEY = 'dedicated-test-key'
    settings.LLM_REASONING_EFFORT = 'low'
    client = get_llm_client()
    assert isinstance(client, GroqClient)
    with mock.patch('chat_pipeline.llm.requests.post') as post:
        post.return_value.status_code = 200
        post.return_value.json.return_value = {'choices': [{'message': {'content': 'Grounded answer'}}]}
        assert client.complete('SYSTEM', 'USER') == 'Grounded answer'
    assert post.call_args.args[0] == 'https://api.groq.com/openai/v1/chat/completions'
    assert post.call_args.kwargs['headers']['Authorization'] == 'Bearer dedicated-test-key'
    assert post.call_args.kwargs['json']['reasoning_effort'] == 'low'


def test_groq_can_use_generic_key_and_custom_gateway(settings):
    settings.LLM_PROVIDER = 'groq'
    settings.GROQ_API_KEY = ''
    settings.LLM_BASE_URL = 'https://gateway.example/v1/'
    client = get_llm_client()
    assert client.api_key == settings.LLM_API_KEY
    assert client.base_url == 'https://gateway.example/v1'


def test_optional_provider_reasoning_setting(settings):
    settings.LLM_REASONING_EFFORT = 'low'
    with mock.patch.object(OpenAICompatibleClient, '_post', return_value={'choices': [{'message': {'content': 'Answer'}}]}) as post:
        assert OpenAICompatibleClient().complete('SYSTEM', 'USER') == 'Answer'
    assert post.call_args.args[2]['reasoning_effort'] == 'low'


def test_other_providers_receive_no_extra_setting_by_default(settings):
    settings.LLM_REASONING_EFFORT = ''
    with mock.patch.object(OpenAICompatibleClient, '_post', return_value={'choices': [{'message': {'content': 'Answer'}}]}) as post:
        OpenAICompatibleClient().complete('SYSTEM', 'USER')
    assert 'reasoning_effort' not in post.call_args.args[2]
