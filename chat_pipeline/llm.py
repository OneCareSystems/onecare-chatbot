"""CHAT-09: the LLM call. Plain HTTP (requests), no vendor SDK. Providers: openai_compatible | openai_compatible | fake.
One short retry only for transient errors. The API key and the prompt text are NEVER logged."""
import logging
import re
import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import requests
from django.conf import settings

from .errors import ChatPipelineError

logger = logging.getLogger(__name__)
RETRY_STATUS = {429, 500, 502, 503, 504, 529}


class LLMUnavailable(ChatPipelineError):
    """The LLM failed, timed out, is not configured, or returned something unusable."""


class _HttpClient:
    default_base_url = ""

    def __init__(self):
        s = settings
        self.api_key = getattr(s, "LLM_API_KEY", "") or ""
        self.model = getattr(s, "LLM_MODEL", "") or ""
        self.base_url = (getattr(s, "LLM_BASE_URL", "") or self.default_base_url).rstrip("/")
        self.max_tokens = int(getattr(s, "LLM_MAX_TOKENS", 400))
        self.temperature = getattr(s, "LLM_TEMPERATURE", 0.0)
        self.timeout = (getattr(s, "LLM_CONNECT_TIMEOUT", 3), getattr(s, "LLM_TIMEOUT_SECONDS", 20))
        self.retries = max(0, int(getattr(s, "LLM_MAX_RETRIES", 1)))
        self.backoff = float(getattr(s, "LLM_RETRY_BACKOFF_SECONDS", 0.5))

    def _post(self, url, headers, body):
        if not self.api_key or not self.model:
            raise LLMUnavailable("LLM_API_KEY and LLM_MODEL must be configured.")
        attempts, last = 1 + self.retries, "unknown"
        for attempt in range(1, attempts + 1):
            response = None
            try:
                response = requests.post(url, headers=headers, json=body, timeout=self.timeout)
            except requests.RequestException as exc:
                last = exc.__class__.__name__
            else:
                if response.status_code == 200:
                    try:
                        return response.json()
                    except ValueError as exc:
                        raise LLMUnavailable("The LLM returned invalid JSON.") from exc
                last = f"HTTP {response.status_code}"
                if response.status_code == 429:
                    last += " (provider rate limit or quota exceeded)"
                    try:
                        error = response.json().get("error", {})
                        quota_exhausted = isinstance(error, dict) and any(
                            error.get(field) in ("insufficient_quota", "billing_hard_limit_reached")
                            for field in ("code", "type")
                        )
                    except (ValueError, AttributeError):
                        quota_exhausted = False
                    if quota_exhausted:
                        last = "HTTP 429 (provider quota exhausted; check provider billing and quota)"
                        break
                if response.status_code not in RETRY_STATUS:
                    break                                           # 400/401/403/404: retrying cannot help
            if attempt < attempts:
                delay = self.backoff * (2 ** (attempt - 1))
                if response is not None and response.status_code in RETRY_STATUS:
                    retry_after = response.headers.get("Retry-After")
                    if retry_after:
                        try:
                            delay = max(0.0, float(retry_after))
                        except (TypeError, ValueError):
                            try:
                                retry_at = parsedate_to_datetime(retry_after)
                                if retry_at.tzinfo is None:
                                    retry_at = retry_at.replace(tzinfo=UTC)
                                delay = max(0.0, (retry_at - datetime.now(UTC)).total_seconds())
                            except (TypeError, ValueError, OverflowError):
                                pass
                time.sleep(delay)
        logger.error("LLM call failed (%s) after %d attempt(s)", last, attempt)
        raise LLMUnavailable(f"The LLM request failed ({last}).")


class openai_compatibleClient(_HttpClient):
    default_base_url = "https://api.openai_compatible.com"

    def complete(self, system, user):
        body = {"model": self.model, "max_tokens": self.max_tokens, "system": system,
                "messages": [{"role": "user", "content": user}]}
        if self.temperature is not None:
            body["temperature"] = self.temperature
        data = self._post(f"{self.base_url}/v1/messages",
                          {"x-api-key": self.api_key, "openai_compatible-version": "2023-06-01", "content-type": "application/json"}, body)
        blocks = data.get("content")
        if not isinstance(blocks, list):
            raise LLMUnavailable("The LLM response has no content.")
        return "".join(b.get("text", "") for b in blocks if isinstance(b, dict) and b.get("type") == "text").strip()


class OpenAICompatibleClient(_HttpClient):
    """OpenAI, Azure-style gateways, Ollama (http://localhost:11434/v1), vLLM, LM Studio ... any /chat/completions API."""
    default_base_url = "https://api.openai.com/v1"

    def complete(self, system, user):
        body = {"model": self.model, "max_tokens": self.max_tokens,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        effort = getattr(settings, 'LLM_REASONING_EFFORT', '')
        if effort:
            body['reasoning_effort'] = effort
        if self.temperature is not None:
            body["temperature"] = self.temperature
        data = self._post(f"{self.base_url}/chat/completions",
                          {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}, body)
        try:
            return (data["choices"][0]["message"]["content"] or "").strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMUnavailable("The LLM response has no content.") from exc


class FakeLLMClient:
    """For local tests with no API key: answers with the first sentence of the first context block, a fixed Tamil
    sentence for Tamil, and NO_ANSWER when there is no context. It is NOT a language model."""
    model = "fake"

    def complete(self, system, user):
        if "Reply language: Tamil" in user:
            return "\u0b87\u0ba4\u0bc1 \u0b92\u0bb0\u0bc1 \u0b9a\u0bcb\u0ba4\u0ba9\u0bc8 \u0baa\u0ba4\u0bbf\u0bb2\u0bcd. \u0b89\u0ba3\u0bcd\u0bae\u0bc8\u0baf\u0bbe\u0ba9 \u0bae\u0bca\u0bb4\u0bbf \u0bae\u0bbe\u0ba4\u0bbf\u0bb0\u0bbf \u0b87\u0ba3\u0bc8\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bb5\u0bbf\u0bb2\u0bcd\u0bb2\u0bc8."
        match = re.search(r'<source id="1">\n(.*?)\n</source>', user, re.DOTALL)
        if not match:
            return "NO_ANSWER"
        return re.split(r"(?<=[.!?])\s", match.group(1).strip())[0]


def get_llm_client():
    provider = (
        getattr(settings, "LLM_PROVIDER", "openai_compatible") or ""
    ).lower()

    clients = {
        "openai_compatible": OpenAICompatibleClient,
        "fake": FakeLLMClient,
    }

    if provider not in clients:
        raise LLMUnavailable(
            f"Unknown LLM_PROVIDER '{provider}'."
        )

    return clients[provider]()
# def get_llm_client():
#     provider = (getattr(settings, "LLM_PROVIDER", "openai_compatible") or "").lower()
#     clients = {"openai_compatible": openai_compatibleClient, "openai_compatible": OpenAICompatibleClient, "fake": FakeLLMClient}
#     if provider not in clients:
#         raise LLMUnavailable(f"Unknown LLM_PROVIDER '{provider}'.")
#     return clients[provider]()
