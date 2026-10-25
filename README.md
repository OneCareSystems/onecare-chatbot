The **OneCare AI Chatbot** is a standalone Django service for the OneCare Clinic Integrated Pharmacy Management System. It provides English and Tamil chatbot responses, retrieves information from an approved knowledge base, and integrates with the Spring Boot backend.

> **Integration:** React frontend → Spring Boot backend → Django chatbot. The Django `/internal/*` endpoints are service-to-service APIs, not public browser endpoints.

## Technology stack

| Area | Technology |
|---|---|
| Language/runtime | Python 3.11.9 |
| Web framework | Django 5.2 series, Django REST Framework |
| Database | MySQL 8.0 (dedicated chatbot database) |
| Retrieval | Sentence Transformers, FAISS |
| Language support | English, Tamil, language detection |
| Content ingestion | PDF extraction and approved website links |
| Generation | Configurable LLM provider or extractive generator |
| Testing | pytest, pytest-django |
| Code/security checks | Ruff, pinned dependencies, pip-audit |
| Deployment | Docker, Docker Compose, Gunicorn |

Exact installed versions are pinned in `requirements.txt` and `requirements-dev.txt`.

## Main features

- **Multilingual questions:** Handles English and Tamil queries, including fixed clinic information.
- **Retrieval-augmented responses:** Searches indexed knowledge-base passages and applies confidence thresholds.
- **Knowledge-base management:** Accepts PDF documents and approved website links, extracts content, chunks it, creates embeddings, and indexes passages.
- **Medical safety controls:** Rejects requests for diagnosis, prescriptions, and dosage advice; filters generated responses and uses safe fallback messages when needed.
- **Clinic integration:** Supports clinic-information routing and fixed answers, with integration options for the Spring Boot service.
- **Internal API security:** Uses a shared service token for Spring Boot–Django communication.
- **Logging and maintenance:** Includes chat logging/reporting, log cleanup, ingestion-worker, and evaluation commands.

The chatbot is an informational assistant, **not** a replacement for a medical professional.

## Architecture

```text
React Frontend
      |
      v
Spring Boot Backend (:8080)
  |   - public chatbot API
  |   - input validation and rate limiting
  |   - protected knowledge-base administration
      |
      | Bearer service token
      v
Django Chatbot (:8000)
  |-- Query validation and language detection
  |-- Medical guardrails / clinic answers
  |-- Knowledge-base retrieval (embeddings + FAISS)
  |-- Confidence checking
  |-- Response generation / output filtering
  |-- Fallback responses
  |
  +-- MySQL chatbot database
  +-- Knowledge-base files and vector index
  +-- Optional external LLM provider
```

The chatbot database is separate from the Spring Boot application database.

## Repository structure

```text
onecare-chatbot/
├── chat_pipeline/        # Query processing, retrieval, safety, LLM and logging
├── knowledgebase/         # PDF/link ingestion, validation, embeddings and indexing
├── onecare_chat/          # Django configuration, routing and service authentication
├── vectorstore/           # Embedding model configuration
├── tests/                 # Unit, API, integration and security tests
├── scripts/               # Dependency pin and environment helper scripts
├── db/                    # Chatbot database provisioning
├── docker/mysql/init/     # MySQL initialization
├── docs/                  # Architecture and feature documentation
├── tools/mock_spring.py   # Local stand-in for Spring clinic API
├── .github/workflows/ci.yml
├── requirements.in
├── requirements.txt
├── requirements-dev.txt
├── .env.example
├── Dockerfile
├── docker-compose.yml
└── manage.py
```

## Prerequisites

- Git
- Docker Desktop with Docker Compose (**recommended**)
- For running outside Docker: Python 3.11, MySQL 8.0, and required build libraries for Python dependencies
- Spring Boot backend for full application integration
- An LLM API key **only if** using an external LLM generator

## Getting started (Docker Compose)

### 1. Clone the repository

```powershell
git clone https://github.com/OneCareSystems/onecare-chatbot.git
cd onecare-chatbot
```

### 2. Configure environment variables

```powershell
Copy-Item .env.example .env
```

Edit `.env` and replace placeholder values. In particular, generate a strong `DJANGO_SECRET_KEY` and `CHATBOT_SERVICE_TOKEN`. The service token must match the Spring Boot backend's `CHATBOT_SERVICE_TOKEN`.

Example of essential local settings:

```dotenv
DB_NAME=onecare_chatbot
DB_USER=chatbot_app
DB_PASSWORD=replace-with-local-password
MYSQL_ROOT_PASSWORD=replace-with-local-root-password
MYSQL_HOST_PORT=3307

DJANGO_SECRET_KEY=replace-with-generated-random-secret
DJANGO_DEBUG=0
ALLOWED_HOSTS=localhost,127.0.0.1,chatbot
CHATBOT_SERVICE_TOKEN=replace-with-long-random-service-token

KB_URL_ALLOWLIST=who.int,nhs.uk,cdc.gov
```

Generate a random secret in PowerShell:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Use **different** generated values for the Django secret and service token. Keep `.env` out of Git. Review the full `.env.example` for optional retrieval, model, and clinic settings. Some example fields are placeholders and must not be copied unchanged into production.

### 3. Build and start services

```powershell
docker compose up -d --build
docker compose ps
docker compose logs -f chatbot
```

The Compose file starts:

| Service | Host address |
|---|---|
| Django chatbot | `http://localhost:8000` |
| MySQL | `localhost:3307` by default |

Inside the Compose network, Django connects to MySQL at `db:3306`.

### 4. Verify health

The health endpoint requires the service token:

```powershell
$headers = @{ Authorization = "Bearer $env:CHATBOT_SERVICE_TOKEN" }
Invoke-RestMethod -Uri "http://localhost:8000/internal/health" -Headers $headers
```

If the token is only in `.env`, load its value into the PowerShell session first. Expected response:

```json
{"status": "ok"}
```

An unauthenticated request should be rejected.

### 5. Stop services

```powershell
docker compose down
```

Do not use `docker compose down -v` unless you intentionally want to remove persistent database and chatbot storage volumes.

## Running locally without Docker

Start MySQL separately and create the dedicated `onecare_chatbot` database and restricted user. Set `DB_HOST=127.0.0.1` and `DB_PORT` to the **host** MySQL port (for example, `3307` when using the Compose database).

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python manage.py migrate
python manage.py runserver 127.0.0.1:8000
```

Django needs the required environment variables from `.env` loaded into the process. Use `scripts/load-env.ps1` where appropriate or set them explicitly in your terminal. The database must already be reachable before running migrations.

For deployment, use Gunicorn (as configured in `Dockerfile`), not Django's development server.

## Internal API endpoints

The following routes are defined in `onecare_chat/urls.py`:

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/internal/health` | Authenticated health check |
| `POST` | `/internal/chat/query` | Process a chatbot question |
| `POST` | `/internal/knowledge-base` | Upload a knowledge-base PDF |
| `POST` | `/internal/knowledge-base/links` | Submit an approved website link |
| `GET` | `/internal/knowledge-base/<doc_id>` | Retrieve knowledge-document details |

The health and chat-query routes also support a trailing slash. Internal requests require `Authorization: Bearer <CHATBOT_SERVICE_TOKEN>`. Knowledge-base management is intended to be accessed through the Spring Boot role-protected API.

### Example: chatbot query

```powershell
$headers = @{
  Authorization = "Bearer $env:CHATBOT_SERVICE_TOKEN"
  "Content-Type" = "application/json"
}
$body = @{ query = "What are the clinic opening hours?" } | ConvertTo-Json

Invoke-RestMethod `
  -Uri "http://localhost:8000/internal/chat/query" `
  -Method Post `
  -Headers $headers `
  -Body $body
```

The request body is:

```json
{"query": "What are the clinic opening hours?"}
```

The response depends on the query and the configured clinic, knowledge-base, and generator settings. Supported result types include `ANSWER`, `REFUSAL`, `FALLBACK`, and `CLINIC_FACT`.

**Important:** The current chat-query implementation describes anonymous patient questions; it does **not** require an `X-OneCare-User-Id` header. Do not use older integration examples that mandate this header for every chat request.

## Knowledge-base processing

```text
PDF upload / approved URL
        ↓
Source validation and extraction
        ↓
Language detection
        ↓
Text chunking
        ↓
Embedding generation
        ↓
FAISS indexing
        ↓
Semantic retrieval for chatbot questions
```

Website ingestion is restricted using `KB_URL_ALLOWLIST` and URL safety checks. An empty allowlist rejects submitted website links. The vector index and uploaded files use chatbot-specific storage rather than the Spring Boot database.

Knowledge-base management implementation details are documented in `docs/knowledge-base-management.md`.

## LLM and retrieval configuration

Relevant optional environment variables include:

| Variable | Purpose |
|---|---|
| `CHAT_GENERATOR_CLASS` | Selects the response generator |
| `LLM_PROVIDER` | Selects the LLM provider |
| `LLM_BASE_URL` | Provider API base URL |
| `LLM_API_KEY` | Private provider credential |
| `LLM_MODEL` | Provider model identifier |
| `EMBEDDING_MODEL` | Embedding model identifier |
| `CHAT_SCORE_THRESHOLD_EN` | English retrieval-confidence threshold |
| `CHAT_SCORE_THRESHOLD_TA` | Tamil retrieval-confidence threshold |
| `CHAT_SEARCH_TIMEOUT_SECONDS` | Retrieval timeout |
| `KB_URL_ALLOWLIST` | Approved website domains |
| `CHAT_FIXED_CLINIC_ENABLED` | Fixed clinic-answer support |

An external LLM requires a valid provider endpoint, supported model, API key, and available quota. HTTP `401`, `429`, or `503` responses may be provider-side failures, not Django startup errors. Do not commit API keys.

## Testing

Install the development dependencies before running checks:

```powershell
python -m pip install -r requirements-dev.txt
```

Run the standard test suite:

```powershell
pytest -m "not embedding"
```

Run embedding tests separately:

```powershell
pytest -m embedding
```

Run code-quality and dependency checks:

```powershell
ruff check .
python scripts/check_pins.py
pip-audit -r requirements.txt --no-deps --disable-pip --vulnerability-service osv
```

Some tests require a running MySQL instance, test-schema permissions, or a cached embedding model. Check `pytest.ini`, `tests/conftest.py`, and `.github/workflows/ci.yml` for their requirements.

Additional management commands include:

```powershell
python manage.py chat_prompt_eval
python manage.py chat_search_benchmark
python manage.py chat_log_report
python manage.py purge_chat_logs
```

Review each command's options before using it. Prompt evaluation with a live LLM can incur provider charges and rate limits.

## CI/CD

The GitHub Actions workflow is located at:

```text
.github/workflows/ci.yml
```

The repository contains automated checks for dependency pins, Ruff linting, pytest, embedding and database tests, dependency vulnerability auditing, and Docker image building. Certain jobs require MySQL and may download or cache embedding models.

A configured CI check is **not proof that the latest workflow passed**. Review the GitHub Actions results for the specific commit before reporting release readiness.

## Security considerations

- Keep service tokens, Django secrets, database passwords, and LLM keys outside version control.
- Expose Django internal endpoints only to trusted backend services in deployed environments.
- Enforce staff role authorization in Spring Boot for knowledge-base operations.
- Restrict external website ingestion to reviewed domains.
- Apply medical guardrails, output filtering, and fallback responses.
- Use a dedicated database account with minimum necessary permissions.
- Review logs and retention settings before processing real patient information.
- Complete security tests and vulnerability reviews before production deployment.

## Troubleshooting

| Problem | What to check |
|---|---|
| MySQL connection refused | Database running; `DB_HOST` and `DB_PORT` correct for host versus Docker network |
| Health endpoint returns `401` | `Authorization` header and shared service token |
| Website link rejected | Domain is in `KB_URL_ALLOWLIST` and passes URL safety checks |
| Chatbot returns fallback | Indexed content, confidence threshold, generator configuration, and service availability |
| LLM returns `401` | API key, endpoint, and model authorization |
| LLM returns `429` | Provider quota, billing, and rate limits |
| Embedding tests fail | Model availability, cache, memory, and test environment |
| `pip-audit` fails | Review reported vulnerabilities and update approved dependency pins |

## Related repositories

- [OneCare Frontend](https://github.com/OneCareSystems/onecare-frontend)
- [OneCare Backend](https://github.com/OneCareSystems/onecare-backend)
- [OneCare Chatbot](https://github.com/OneCareSystems/onecare-chatbot)

## License

See the repository's `LICENSE` file.
"""
path = Path("/mnt/data/OneCare_Chatbot_README.md")
path.write_text(readme, encoding="utf-8")
print(path, len(readme.splitlines()), "lines")
