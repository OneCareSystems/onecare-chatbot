# Clinic answers and healthcare resources

The application still uses React → Spring Boot → Django → Spring Boot → React.
No Django credential is sent to the browser. No migration or model replacement is required.

## Routing and language

1. Existing input validation and language detection run first.
2. Existing pre-generation guardrails run before configured clinic answers.
3. `chat_pipeline/fixed_answers.py` normalizes Unicode, whitespace, case and terminal
   punctuation, then matches complete English or Tamil question patterns. It does
   not classify arbitrary questions by a single keyword. Extend `PATTERNS` with
   reviewed complete-question patterns when adding paraphrases.
4. Recognized hours, today's generic doctor availability, booking and services
   return `CLINIC_FACT` in the detected language (`EN` or `TA`). Hours are 5:00 PM–11:00 PM.
   Eight numbered services are preserved. `clinicInfoSource: CONFIGURED` in the
   internal response distinguishes configured information from live slot checks.
5. Unmatched clinic questions still use the existing Spring clinic client, including
   named doctors and tomorrow's availability. Questions naming another clinic do
   not invoke OneCare's live clinic client.
6. Other questions continue through FAISS, the existing language-specific confidence
   thresholds, existing LLM generator, language checks, output filter and fallbacks.

`CHAT_FIXED_CLINIC_ENABLED=true` is the default. Set it to `false` for the original
live-only clinic behavior. Django deployments can override individual approved
templates using `CHAT_FIXED_CLINIC_ANSWERS = {intent: {language: template}}` in settings.
The bundled Tamil answers describe the configured 5:00 PM–11:00 PM schedule; update
both translations together if the schedule changes.

The existing chips file is unchanged: same IDs, labels, queries and order. There
are no healthcare-topic chips and no frontend healthcare answer database.

## Booking action

Django returns `action: {type: "BOOK_APPOINTMENT"}` only for the recognized booking
intent. Spring validates that action and exposes `action: "BOOK_APPOINTMENT"` only
on `CLINIC_FACT`. Existing constructors remain available for compatibility.

The widget displays **Book Appointment** / **நேரம் முன்பதிவு செய்க**, then emits
`onecare-chat:book-appointment` only on click. HomePage handles that event with
React Router's `navigate`. URLs in model output are never navigation destinations.

There is no patient booking page in the inspected React router. At the user's
explicit request, `/appointments` remains a placeholder destination. Until that
page exists, the current router displays its normal not-found page there. Replace
the constant in HomePage when the real route is implemented; preserve its auth guard.

## Ingestion and index maintenance

The six canonical website URLs and two PDF filenames are declared in
`knowledgebase/health_resources.py`. Nothing is scraped or fabricated by React.

`setup_health_resources` uses the existing PDF validation/storage/audit service,
URL validation/SSRF checks, document status handling and ingestion worker. Web
sources are deduplicated by normalized URL hash; PDFs by content SHA-256. An index
advisory lock serializes registration by this command. Existing documents are
reused. FAILED documents require `--retry-failed`; INDEXED documents are not
silently re-embedded. Every failure is printed and produces a nonzero exit status.
The existing chunker, embedder, staging/version activation and FAISS index builder
perform ingestion. No browser-visible copies of the PDFs are created.

All six websites were initially blocked by `KB_URL_ALLOWLIST`. The local `.env`
now includes these domains while preserving the previous entries. Other deployments
must configure the same allowlist in Django and Spring before registration:

```dotenv
KB_URL_ALLOWLIST=<existing entries>,diabetes.org,myfoothold.org,megawecare.com,mayoclinic.org,fpasrilanka.org
CHAT_FIXED_CLINIC_ENABLED=true
```

Do not use the literal `<existing entries>` placeholder. Redirect destinations
remain subject to the existing allowlist and public-IP checks. A fetch or extraction
failure is reported as FAILED rather than replaced with invented content.

Both supplied local PDFs were readable: NNP-English-book.pdf yielded 109,029
characters and 10-Tips-Healthy-Lifestyle.pdf yielded 5,000 characters. Extraction
alone does not mean that they have been registered, embedded or indexed.

### Windows PowerShell

Run from `B:\swees\DevelopmentProject\OneCare\onecare-chatbot`:

```powershell
# Replace this with an existing administrator's external ID for audit attribution.
$adminId = '42' # User-supplied ID; verify this is the intended administrator.
.\venv\Scripts\python.exe manage.py setup_health_resources --actor $adminId --ingest
# Retry previously FAILED sources after resolving the reported cause:
.\venv\Scripts\python.exe manage.py setup_health_resources --actor $adminId --ingest --retry-failed
# Process the existing pending queue:
.\venv\Scripts\python.exe manage.py run_ingestion_worker --once
# Rebuild FAISS from existing vectors (does not fetch sources or change embeddings):
.\venv\Scripts\python.exe manage.py run_ingestion_worker --rebuild-index
# Re-extract and re-embed one INDEXED document, replacing its active version:
.\venv\Scripts\python.exe manage.py run_ingestion_worker --reindex 123
.\venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

Existing chatbot database, service-token, Spring URL, LLM provider/key/model and
storage settings remain required. Use the existing `.env`; do not expose tokens
as frontend variables. The user supplied administrator ID `42` for registration.
Spring's `KB_URL_ALLOWLIST` environment must include the same approved domains;
changing the Django `.env` does not change an already-running Spring process.

From `onecare-backend`, start Spring with `./mvnw.cmd spring-boot:run`.
From `onecare-frontend`, start Vite with `npm.cmd run dev`, then visit `/home`.

## Multilingual retrieval

The configured embedder is `intfloat/multilingual-e5-small`. Both indexing and query
embedding already use that same model, normalized vectors and the required
`passage:` / `query:` prefixes. Retrieval filters document status/version, not source
language, so Tamil questions can retrieve English documents. The existing generation
prompt requires the detected response language regardless of source language; the
existing output language check remains enabled. Thresholds are unchanged.

A focused pipeline test verifies English-source context reaches Tamil generation
and that Tamil text and original source citations are returned. A separate real-model
test checks Tamil-to-English semantic ranking when the configured model is cached.
It skips explicitly if the model is unavailable locally, rather than downloading
models or pretending that mocked retrieval proves semantic quality. Live quality
with the actual eight indexed sources still requires model availability, successful
ingestion and the configured LLM.

## Verification commands

```powershell
# From onecare-chatbot (use a fresh basetemp name for subsequent runs):
.\venv\Scripts\python.exe -m pytest tests/test_fixed_clinic_answers.py tests/test_health_resources.py tests/test_health_resource_embeddings.py -q -p no:cacheprovider --basetemp=.test-tmp-health
# Existing regression suites:
.\venv\Scripts\python.exe -m pytest tests/test_chat01_language.py tests/test_chat02_guardrail.py tests/test_chat03_refusal.py tests/test_chat04_search.py tests/test_chat05_fallback.py tests/test_chat06_post_filter.py tests/test_chat07_clinic.py tests/test_chat08_prompt.py tests/test_chat09_generation.py tests/test_chat_pipeline.py -q -p no:cacheprovider --basetemp=.test-tmp-regression-local
# From onecare-backend:
.\mvnw.cmd '-Dtest=ChatBackendResultTest,ChatQueryServiceTest,PublicQueryEndpointTest' test
# From onecare-frontend:
npx.cmd vitest run --config vite.config.js test/chatbot test/pages/ChatFixedAnswers.test.jsx test/pages/HomePage.test.jsx
npm.cmd run build
npm.cmd run lint
```

If the sandbox cannot scan the unrelated `.pytest_cache` directory, use
`npx.cmd eslint . --ignore-pattern .pytest_cache/`.

The explicit Vite config is needed because the existing `vitest.config.js` selects
`tests/**/*.test.js`, whereas these existing UI suites live under `test/`.

## File inventory

New files:

| File | Purpose |
| --- | --- |
| `chat_pipeline/fixed_answers.py` | Approved bilingual answers and precise clinic intent patterns |
| `knowledgebase/health_resources.py` | Canonical resource manifest |
| `knowledgebase/management/commands/setup_health_resources.py` | Repeatable registration/ingestion with accurate per-source failures |
| `tests/test_fixed_clinic_answers.py` | Intent, language, configured information and safety tests |
| `tests/test_health_resources.py` | Validation, PDF extraction, deduplication, cross-language pipeline tests |
| `tests/test_health_resource_embeddings.py` | Optional real-model semantic retrieval check |
| `docs/clinic-health-integration.md` | Setup, behavior, limits and verification documentation |

Modified files, relative to the corresponding application:

| Application / files | Purpose |
| --- | --- |
| Django: `chat_pipeline/service.py` | Fixed answers after safety checks; retain live clinic and RAG |
| Django: `onecare_chat/settings.py`, `.env.example`, local `.env` | Configured-answer switch and allowlist additions preserving prior domains |
| Django: `tests/test_chat07_clinic.py` | Explicitly test retained live-only mode; existing assertions retained |
| Spring: `chatbot/query/ChatBackendResult.java`, `ChatQueryResponse.java`, `ChatQueryService.java` under `src/main/java/com/onecare/backend` | Validate and forward optional booking action; preserve existing constructors |
| Spring: corresponding `ChatBackendResultTest.java`, `ChatQueryServiceTest.java` under `src/test/java/com/onecare/backend` | Action validation and public forwarding tests |
| React: `src/components/chatbot/api.js` | Parse only the approved structured booking action |
| React: `src/components/chatbot/text.js` | Retain Unicode code-point counting while fixing the pre-existing unused-variable lint error |
| React: `src/components/chatbot/onecare-chat-widget.js` | Send all queries through API; render approved booking button |
| React: `src/pages/public/HomePage.jsx` | Handle explicit booking clicks using React Router |
| React: `test/pages/ChatFixedAnswers.test.jsx`, `HomePage.test.jsx` | Server-owned replies, no auto-navigation, route handling |
| React: `test/chatbot/helpers.js`, `api.test.js`, `text.test.js`, `i18n.test.js`, `widget-ui01.test.js`, `widget-ui02.test.js`, `widget-ui03.test.js` | Repair pre-existing relative imports so regression tests run |

Removed `onecare-frontend/src/components/chatbot/fixed-answers.js`: the same approved
clinic topics now live in Django rather than bypassing backend safety in React.

## Results from this implementation

- Django: 262 focused regression tests passed, including configured clinic answers,
  language detection, guardrails, refusals, search, confidence fallback, output
  filters, retained live clinic integration, prompts, generation and pipeline.
- Resource tests: 12 passed, including both real PDFs, safe URL validation,
  deduplication, Tamil generation with English context, and real multilingual
  embedding ranking. The real-model test did not skip.
- Frontend: 135 widget/integration tests passed; the subsequently added React Router
  booking test also passed (5 tests in the updated page suites). Unicode helper
  tests passed after the lint cleanup. Production build passed with existing bundle
  size and dynamic-import warnings. Full ESLint passed with `.pytest_cache` excluded.
- Spring: the original 47 focused tests passed; the updated unit classes then
  passed all 19 tests, including the two new action tests. The public endpoint suite
  accounts for the other 30 tests. No test failures remain in these selected suites.
- Ruff passed for all newly added Python modules and tests.
- Resource registration originally failed while MySQL/Docker were stopped. It was
  rerun successfully once the database became available, using user-supplied audit
  actor `42`: documents 3 (ADA), 5 (Megawecare), 8 (FPA Sri Lanka), 9 (NNP PDF), and
  10 (healthy-lifestyle PDF) are INDEXED. Documents 4, 6 and 7 remain FAILED with
  their actual HTTP 403 fetch errors.
- The allowlist was corrected and all six canonical URLs subsequently passed the
  existing URL/public-address validation. Three sites returned HTTP 403 through
  the protected fetcher: Foothold and both Mayo Clinic URLs. These restrictions were
  not bypassed. Initial extraction attempts on the other sites revealed that the
  existing pinned `trafilatura==2.3.1` dependency was missing from the local venv.
  That pinned dependency was installed, then extraction succeeded for the ADA
  diabetes page (3,170 characters), Megawecare page (6,541 characters), and FPA
  Sri Lanka page (4,335 characters). These successful extractions are not indexing.

The repository's Maven wrapper could not initialize in this shell; tests were run
with the already installed Maven 3.9.15 distribution under the user's `.m2/wrapper`
directory and the existing `.m2/repository` dependency cache.

If using the existing Docker Compose database, start Docker Desktop first, then
run `docker compose up -d db` from the chatbot directory. Verify the host-side
`DB_PORT` matches its published port (default `3307`). Run existing migrations with
`venv\Scripts\python.exe manage.py migrate`, then rerun resource setup. No new
migration was introduced by this change.

## Follow-up: unavailable replies in the live widget

The live integration exposed an HTTP framing problem that mocked service tests
did not catch: Spring's streamed JSON Map used chunked transfer encoding, while
Django's WSGI development server read an empty body and returned HTTP 400. The same
JSON sent with Content-Length returned the expected clinic answer.

`ChatQueryClient` now serializes JSON to UTF-8 bytes and sends the exact byte length.
The new `ChatQueryClientTest` uses a real local HTTP server to verify framing, JSON
escaping and Tamil text, without exposing the service credential. The three focused
Spring unit suites passed all 20 tests.

The embedding model initially needed about 29 seconds to initialize, exceeding the
existing 5-second search deadline. `KB_PRELOAD_EMBEDDER=true` now warms it before
WSGI/ASGI accept requests. `KB_EMBEDDING_LOCAL_FILES_ONLY=true` uses the verified
cached model without network metadata checks. These are optional settings; their
default is false for other installations. Cache/download the model before enabling
local-only mode. A restart is needed after changing `.env`.

The original Gemini 3.8 Flash model timed out or returned HTTP 503 for full healthcare
prompts. At the user's explicit request, another advertised Flash model was tested;
Gemini 3.7 Flash produced a grounded answer and became the local configured model.
The Gemini provider supports the optional `reasoning_effort` parameter documented
in [Google's OpenAI compatibility guide](https://ai.google.dev/gemini-api/docs/openai#thinking).
`LLM_REASONING_EFFORT=low` is enabled locally; it is omitted for other providers by
default. Existing safety checks, confidence thresholds, retry behavior and fallback
handling remain active.

Current local settings:

```dotenv
# onecare-chatbot/.env
LLM_MODEL=gemini-3.7-flash
LLM_REASONING_EFFORT=low
LLM_TIMEOUT_SECONDS=30
CHAT_CONTEXT_CHUNKS=2
KB_PRELOAD_EMBEDDER=true
KB_EMBEDDING_LOCAL_FILES_ONLY=true

# onecare-backend/.env
CHATBOT_READ_TIMEOUT=80s
```

HomePage configures `timeout-ms="90000"` so the browser waits beyond the Spring
deadline. Spring maps `CHATBOT_READ_TIMEOUT` with a 60-second default elsewhere.
The context budget limits both the chunks supplied to generation and the cited
sources, so excluded chunks cannot appear as citations.

Additional changed files: Spring `ChatQueryClient.java`, `application.properties`,
local `.env`; React `HomePage.jsx`; Django `knowledgebase/embedding.py`,
`chat_pipeline/llm.py`, `chat_pipeline/service.py`, `onecare_chat/settings.py`,
`onecare_chat/wsgi.py`, `onecare_chat/asgi.py`, `.env.example`, local `.env` and
`tests/test_health_resources.py`. New tests: Spring `ChatQueryClientTest.java`;
Django `tests/test_embedding_startup.py` and `tests/test_reasoning_configuration.py`.

Follow-up verification:

- 127 Django regression tests passed, plus all 12 resource/citation tests.
- 20 Spring client/service/parser tests passed, including the real HTTP framing test.
- Both HomePage integration tests and targeted frontend lint passed.
- Ruff passed for the changed Python runtime modules and new tests.
- Live Spring API booking returns CLINIC_FACT with BOOK_APPOINTMENT.
- The exact screenshot question, `give the tips for diabetic patients`, returned
  ANSWER in about 4.7 seconds, with ADA and lifestyle-PDF citations.
- A live Tamil clinic-hours question returned CLINIC_FACT / TA.
- **Remaining external limitation:** live Tamil healthcare generation received HTTP
  503 from the provider and returned the existing safe fallback. Successful Tamil
  healthcare generation is not claimed. Three source websites also remain blocked
  with HTTP 403; these restrictions have not been bypassed.

Refresh `/home` to load the timeout setting and start a new conversation. Earlier
fallback bubbles in the existing conversation do not change retroactively.
