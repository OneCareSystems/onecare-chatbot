"""Explicit smoke check using the chatbot's configured provider and credentials."""

import os


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "onecare_chat.settings")
    from chat_pipeline.llm import LLMUnavailable, get_llm_client

    try:
        answer = get_llm_client().complete(
            "You are a connection test. Reply with OK only.", "Hello."
        )
    except LLMUnavailable as exc:
        raise SystemExit(str(exc)) from None
    print(answer)


if __name__ == "__main__":
    main()
