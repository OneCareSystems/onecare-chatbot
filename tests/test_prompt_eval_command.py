from unittest import mock

import pytest
from django.core.management import CommandError, call_command

from chat_pipeline.llm import LLMUnavailable, OpenAICompatibleClient


def test_provider_failure_stops_evaluation(capsys):
    with mock.patch("chat_pipeline.management.commands.chat_prompt_eval.LLMGenerator") as generator:
        generator.return_value.generate.side_effect = LLMUnavailable("HTTP 429")
        with pytest.raises(CommandError, match="Evaluation interrupted.*quota/billing"):
            call_command("chat_prompt_eval")
    assert generator.return_value.generate.call_count == 1
    assert "FAIL" not in capsys.readouterr().out


def test_selected_cases_are_paced_and_failed_answer_is_visible(capsys):
    with mock.patch("chat_pipeline.management.commands.chat_prompt_eval.LLMGenerator") as generator, \
            mock.patch("chat_pipeline.management.commands.chat_prompt_eval.time.sleep") as sleep:
        generator.return_value.generate.side_effect = ["Unexpected response", "NO_ANSWER"]
        with pytest.raises(CommandError, match="Prompt evaluation failed"):
            call_command("chat_prompt_eval", "--case", "in_context_english", "--case", "not_in_context", "--interval", "15")
    sleep.assert_called_once_with(15.0)
    output = capsys.readouterr().out
    assert "Actual answer: 'Unexpected response'" in output
    assert "1 passed, 1 failed" in output


@pytest.mark.parametrize("interval", ["-1", "nan", "inf"])
def test_invalid_interval_is_rejected(interval):
    with pytest.raises(CommandError, match="finite, non-negative"):
        call_command("chat_prompt_eval", "--interval", interval)


def test_exhausted_quota_is_not_retried():
    response = mock.Mock(status_code=429)
    response.json.return_value = {"error": {"code": "insufficient_quota"}}
    with (
        mock.patch("chat_pipeline.llm.requests.post", return_value=response) as post,
        mock.patch("chat_pipeline.llm.time.sleep") as sleep,
        pytest.raises(LLMUnavailable, match="quota exhausted"),
    ):
        OpenAICompatibleClient().complete("system", "user")
    post.assert_called_once()
    sleep.assert_not_called()
