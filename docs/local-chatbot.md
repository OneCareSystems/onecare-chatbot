# Run the chatbot locally

Start Spring on port 8080 and Django on port 8000. From `onecare-chatbot`:

```powershell
.\venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000 --noreload
```

Start Vite from `onecare-frontend` with `npm.cmd run dev`. Vite forwards
`/api/chatbot/query` to Spring; Spring authenticates its requests to Django.
Spring and Django must use the same `CHATBOT_SERVICE_TOKEN`.

For Groq, configure `.env` (never commit keys):

```dotenv
LLM_PROVIDER=groq
GROQ_API_KEY=your-groq-key
LLM_MODEL=openai/gpt-oss-120b
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_REASONING_EFFORT=low
LLM_MAX_TOKENS=1200
CHAT_GENERATOR_CLASS=chat_pipeline.generation.LLMGenerator
CHAT_FIXED_CLINIC_ENABLED=true
KB_PRELOAD_EMBEDDER=true
CHAT_CONTEXT_CHUNKS=4
CHAT_CONTEXT_CHARS_PER_CHUNK=2500
CHAT_TRANSLATE_TAMIL_SEARCH=true
CHAT_SEARCH_TIMEOUT_SECONDS=15
```

`LLM_API_KEY` remains supported if `GROQ_API_KEY` is unset. Tamil query
translation adds a provider call to improve retrieval from English documents;
the answer is still generated in Tamil. Translation failure preserves the
original multilingual search. Full chunks are important: truncating a long PDF
chunk before its relevant paragraph can produce `MODEL_NO_ANSWER`.

Both English and Tamil question suggestions appear in the widget. Built-in
clinic answers do not need the model. `CHAT_FIXED_CLINIC_ENABLED=false` selects
live clinic information instead; this requires Spring's internal clinic API.

Register/index the project's six websites and two PDFs using an existing
administrator's ID:

```powershell
.\venv\Scripts\python.exe manage.py setup_health_resources --actor YOUR_ADMIN_ID --ingest --retry-failed
```

Run the ingestion worker for newly uploaded PDFs and submitted links:

```powershell
.\venv\Scripts\python.exe manage.py run_ingestion_worker
```

On 23 October 2026, both project PDFs and the Diabetes Association, Mega We Care,
and FPA Sri Lanka pages were indexed. The My Foothold page and both Mayo Clinic
pages returned HTTP 403 even on retry. Their records correctly remain `FAILED`;
they cannot supply answers until accessible source content is provided. A PDF
copy of an inaccessible page can be uploaded through knowledge base management.

Restart Django after changing `.env` or Python files when using `--noreload`.
If every question shows "temporarily unavailable", first confirm Django is
running. Provider errors affect document generation; they should not affect
configured clinic answers. Check service logs for `GENERATION_UNAVAILABLE`,
`SEARCH_UNAVAILABLE`, or a provider HTTP error without exposing secret values.
