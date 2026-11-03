class ChatPipelineError(Exception):
    """Base class for every typed error of the chat pipeline."""


class PatternConfigError(ChatPipelineError):
    """guardrail_patterns.json is missing, unreadable or invalid. The guardrail fails closed."""


class VectorStoreUnavailable(ChatPipelineError):
    """The vector store failed or timed out. It is NEVER turned into an empty result (CHAT-04 AC2)."""


class ClinicUnavailable(ChatPipelineError):
    """The Spring Boot clinic API failed, timed out, returned 401 or returned unusable data (CHAT-07)."""