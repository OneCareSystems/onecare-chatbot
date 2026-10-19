"""CHAT-09 (LLM generation) is OUTSIDE Stage 3. This placeholder lets the pipeline run end to end without an LLM:
it returns the best retrieved chunk. Replace it by pointing settings.CHAT_GENERATOR_CLASS at the real generator.
A generator may expose a `system_prompt` attribute: CHAT-06 then also blocks answers that repeat it."""
from django.conf import settings
from django.utils.module_loading import import_string


class ExtractiveGenerator:
    system_prompt = None

    def generate(self, query, hits, language):
        return hits[0]["text"]


def get_generator():
    return import_string(getattr(settings, "CHAT_GENERATOR_CLASS", "chat_pipeline.generation.ExtractiveGenerator"))()