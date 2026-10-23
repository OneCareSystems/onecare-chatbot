# onecare-chatbot
Chatbot For OneCare System

## Groq configuration

Set these values in `onecare-chatbot/.env`:

```dotenv
LLM_PROVIDER=groq
GROQ_API_KEY=your-groq-api-key
LLM_API_KEY=
LLM_MODEL=openai/gpt-oss-120b
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_REASONING_EFFORT=low
LLM_MAX_TOKENS=2048
CHAT_GENERATOR_CLASS=chat_pipeline.generation.LLMGenerator
```

Create a key at https://console.groq.com/keys and restart Django after changing
the environment. Existing process environment variables take precedence over `.env`;
reload any variables previously set with `scripts/load-env.ps1` before restarting.
`GROQ_API_KEY` takes precedence over `LLM_API_KEY` for the Groq provider.
The existing HTTP client handles authentication, timeouts, retries, and response
parsing; no Groq SDK installation is required. GPT-OSS reasoning is excluded from
the response, and only the final answer is passed to the chatbot's existing filters.

Check the connection explicitly with `python llm_manual_check.py`.
Provider documentation: https://console.groq.com/docs/openai and
https://console.groq.com/docs/models.
