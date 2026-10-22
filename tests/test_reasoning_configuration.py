from unittest import mock

from chat_pipeline.llm import OpenAICompatibleClient


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
