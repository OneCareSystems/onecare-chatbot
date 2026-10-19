"""Answer generators. The service picks one with settings.CHAT_GENERATOR_CLASS.
  LLMGenerator       - CHAT-09: the real one (system prompt from CHAT-08 + retrieved chunks -> LLM).
  ExtractiveGenerator - Stage 3 stand-in that returns the best chunk. Kept for tests and for running with no LLM at all.
A generator may expose `system_prompt` (CHAT-06 then blocks answers that repeat it) and `info` (logged by CHAT-10)."""
from django.conf import settings
from django.utils.module_loading import import_string

from . import prompts
from .llm import get_llm_client


class ExtractiveGenerator:
    system_prompt = None
    info = {"model": "extractive", "prompt_version": ""}

    def generate(self, query, hits, language):
        return hits[0]["text"]


class LLMGenerator:
    def __init__(self, client=None):
        self.client = client or get_llm_client()
        self.system_prompt = prompts.base_system_prompt()
        self.info = {"model": getattr(self.client, "model", ""), "prompt_version": prompts.PROMPT_VERSION}

    def generate(self, query, hits, language):
        return self.client.complete(self.system_prompt, prompts.build_user_prompt(query, hits, language))


def get_generator():
    return import_string(getattr(settings, "CHAT_GENERATOR_CLASS", "chat_pipeline.generation.LLMGenerator"))()