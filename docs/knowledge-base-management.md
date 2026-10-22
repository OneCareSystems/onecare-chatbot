# Knowledge base PDF and link management

## Existing implementation and incremental changes

Django already supplied PDF uploads, approved-link submission, safe metadata by ID,
soft removal with file/chunk/vector cleanup, a PENDING ingestion queue, and a worker.
Only listing was missing there. Spring previously exposed link submission alone;
its client returned only ID/status. The doctor's Medical Knowledge Base page was
a separate clinical reference library using temporary browser URLs.

The implementation preserves that reference library and adds a clearly labelled
**Chatbot Knowledge Base** management panel below it. The same reusable panel is
available at `/super-admin/knowledge-base`, linked from the Super Admin sidebar.
Patient chat, suggested questions, clinic routing, guardrails and bilingual RAG
behavior were not changed by this task. No new dependency or migration is required.

## API contract

All browser calls use Spring with an existing staff access JWT. The existing KB
role policy remains **DOCTOR or SUPER_ADMIN**; ADMIN and all other roles remain
denied. Spring forwards its server-only service token and the authenticated user
ID, never a browser-supplied actor ID. Django validates the service token and actor
header as before. No KB data is stored in Spring's database.

| Operation | Spring route | Django internal route | Success |
| --- | --- | --- | --- |
| Add PDF | POST `/api/chatbot/knowledge-base` | POST `/internal/knowledge-base` | 201 |
| Add link | POST `/api/chatbot/knowledge-base/links` | POST `/internal/knowledge-base/links` | 202 |
| List resources | GET `/api/chatbot/knowledge-base` | GET `/internal/knowledge-base` | 200 |
| Details | GET `/api/chatbot/knowledge-base/{id}` | GET `/internal/knowledge-base/{id}` | 200 |
| Remove | DELETE `/api/chatbot/knowledge-base/{id}` | DELETE `/internal/knowledge-base/{id}` | 204 |

PDF upload accepts multipart `file` and optional `title`. Django retains content
signature validation and its configurable file-size limit. Spring's default upload
limit is now the matching 10 MiB, rather than the framework's 1 MiB default.
`KB_MAX_UPLOAD_BYTES` controls the file limit in both applications;
`KB_MAX_REQUEST_BYTES` controls Spring's complete multipart request limit, default
11 MiB. Keep the latter above the file limit to allow multipart overhead. Oversized
Spring multipart requests return 413 with a safe message; existing Django file
validation responses remain 400 for backward compatibility.

Link submission accepts JSON `{"url":"https://approved.example/article"}`.
Existing HTTPS, allowlist, DNS/private-address, redirect and duplicate validation
remains authoritative. The domain must be approved in both applications. Neither
submission endpoint fetches/embeds inline: it creates the existing PENDING queue
record. Run the existing ingestion worker to process it.

Listing supports one-based `page` (default 1), `pageSize` (default 20, maximum 100),
optional `sourceType=PDF|WEB`, and optional
`status=PENDING|PROCESSING|INDEXED|FAILED|REMOVED`. Invalid values return 400. The
ordering is newest creation date then descending ID, so pagination is deterministic.
An out-of-range positive page returns empty items. Removed records are excluded
by default; explicitly filter REMOVED to inspect them. Existing detail-by-ID behavior
for removed records remains unchanged and returns their REMOVED metadata.

The Spring JSON envelope remains `{success, message, data}`. Example list data:

```json
{
  "items": [
    {
      "id": 12,
      "title": "Clinic guide",
      "sourceType": "PDF",
      "status": "PENDING",
      "language": null,
      "originalFilename": "guide.pdf",
      "sourceUrl": null,
      "uploadedBy": "42",
      "createdAt": "2026-10-22T10:00:00+00:00"
    }
  ],
  "count": 1,
  "page": 1,
  "pageSize": 20,
  "totalPages": 1
}
```

Other safe existing fields include needsReview and failureReason. Storage paths,
embeddings, content hashes and service credentials are not serialized. Source URL
query strings remain stripped by Django. Spring uses an explicit metadata DTO and
ignores unknown upstream fields. Existing two-argument DTO construction is retained.

## Ingestion and safe removal

Uploads and links use the existing services and PENDING queue. Run:

```powershell
cd B:\swees\DevelopmentProject\OneCare\onecare-chatbot
.\venv\Scripts\python.exe manage.py run_ingestion_worker
```

The worker extracts content, detects language, chunks, embeds, stages an index
version and activates it using the existing code. An idle worker polls every five
seconds by default. `--once` handles the current queue and exits. The UI Refresh
button retrieves current persisted statuses; it does not claim that a PENDING
resource has already been indexed.

Removal still marks REMOVED before cleanup. Retrieval filters status and active
version even if cleanup is temporarily unavailable. The ingestion activation step
checks the status again, preventing removed in-flight documents from reappearing.
Existing worker cleanup retries are preserved. Deleting an already removed resource
still returns 204; a nonexistent ID returns 404. No new physical-deletion policy was
introduced.

## Spring forwarding and error behavior

JSON and multipart bodies carry an explicit Content-Length for Django's WSGI
development server. PDF filenames are reduced to a basename before forwarding.
The current HTTP client and configured connect/read deadlines are reused.

Django 400/404/409/413/415/422 responses retain the appropriate status and a bounded
safe JSON validation message. Raw HTML and internal error bodies are never returned.
Django service-authentication failures, network errors, malformed responses,
timeouts and service failures become 503. A Django token problem does not become
a browser 401 or log the staff user out. Staff authentication/authorization is
still handled by the existing Spring Security configuration.

## Postman and local commands

Import `postman/knowledge-base-management.postman_collection.json`. Set baseUrl to
`http://localhost:8080` and accessToken to a JWT from the application's existing
DOCTOR/SUPER_ADMIN login. Choose a local PDF in request 1. Upload/link requests save
the returned ID to the collection's resourceId variable for the details/removal
requests. The collection contains all five operations and no Django service token.

Equivalent request examples (use Postman's Authorization > Bearer Token):

```text
POST http://localhost:8080/api/chatbot/knowledge-base
Body: form-data; file=<selected PDF>; title=Clinic guide

POST http://localhost:8080/api/chatbot/knowledge-base/links
Content-Type: application/json
Body: {"url":"https://diabetes.org/food-nutrition/eating-healthy"}

GET http://localhost:8080/api/chatbot/knowledge-base?page=1&pageSize=20
GET http://localhost:8080/api/chatbot/knowledge-base?sourceType=WEB&status=INDEXED
GET http://localhost:8080/api/chatbot/knowledge-base/12
DELETE http://localhost:8080/api/chatbot/knowledge-base/12
```

Start the existing MySQL services first. Run these in separate PowerShell terminals:

```powershell
cd B:\swees\DevelopmentProject\OneCare\onecare-chatbot
.\venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000

cd B:\swees\DevelopmentProject\OneCare\onecare-chatbot
.\venv\Scripts\python.exe manage.py run_ingestion_worker

cd B:\swees\DevelopmentProject\OneCare\onecare-backend
.\mvnw.cmd spring-boot:run

cd B:\swees\DevelopmentProject\OneCare\onecare-frontend
npm.cmd run dev
```

Restart backend processes that were started with automatic reload disabled before
trying the new routes. Configure both server-side service tokens to match, set
Spring's Django base URL as before, and keep KB_URL_ALLOWLIST aligned. Existing
database and storage settings remain in effect. No migration command is needed
specifically for this change.

## File inventory

Modified Django files:

- `knowledgebase/services.py`: bounded, stable pagination and validated filters.
- `knowledgebase/views.py`: GET dispatch on the existing PDF collection route.
  Existing root URL mapping already targets that view, so URL files were not changed.

New Django files:

- `tests/test_kb_management.py`: upload validation, mixed listing, pagination,
  filters, safe detail metadata, authentication, missing IDs and removal tests.
- `postman/knowledge-base-management.postman_collection.json`: five public requests.
- `docs/knowledge-base-management.md`: this implementation and verification guide.

Modified Spring files under `src/main/java/com/onecare/backend`:

- `chatbot/knowledgebase/KnowledgeBaseController.java`: expose the four missing
  operations and safe KB-specific upstream-error responses.
- `chatbot/knowledgebase/KnowledgeBaseService.java`: preserve link handling; add
  actor/role checks and service methods for the other operations.
- `chatbot/knowledgebase/KnowledgeBaseClient.java`: backward-compatible client
  extension while retaining the original single abstract link method.
- `chatbot/knowledgebase/DjangoKnowledgeBaseClient.java`: forward all operations,
  identities and filters; prebuffer request bodies for WSGI; map service failures.
- `chatbot/knowledgebase/KnowledgeDocumentResponse.java`: safe metadata fields,
  preserving the existing ID/status constructor.
- `exception/GlobalExceptionHandler.java`: return 413 for oversized multipart input.
- `src/main/resources/application.yml`: matching PDF/multipart size limits in the
  tracked shared configuration (local application.properties is intentionally ignored).

New Spring files in `chatbot/knowledgebase`:

- `KnowledgeDocumentPage.java`: typed paginated response.
- `KnowledgeBaseRequestException.java`: bounded validation/not-found status mapping.
- Under corresponding `src/test/java`: `DjangoKnowledgeBaseClientTest.java` and
  `KnowledgeBaseControllerTest.java` cover forwarding and the five HTTP operations.
- Existing `KnowledgeBaseRbacTest.java` extends denial checks to all new methods.
  The existing class-level permission rule is retained, so SecurityConfig is unchanged.

Frontend additions:

- `src/services/knowledgeBaseService.js`: use the existing authenticated Axios client.
- `src/components/chatbot/KnowledgeBaseManager.jsx`: upload/link forms, filters,
  persisted resource table, details, confirmation, progress and success/error states.
- `src/pages/superAdmin/KnowledgeBaseManagementPage.jsx`: authorized admin screen.
- `test/components/KnowledgeBaseManager.test.jsx` and
  `test/services/knowledgeBaseService.test.js`: management workflows/API integration.

Frontend modifications:

- `src/pages/doctor/KnowledgeBasePage.jsx`: add the shared management panel while
  preserving clinical references, viewing, local additions and local removal.
- `src/routes/AppRoutes.jsx`: add the management page within the existing Super Admin guard.
- `src/constants/navigation.js`: append its sidebar link without reordering existing links.
- `test/routes/appRoutes.integration.test.jsx`: authorized/denied access to the new
  management route; make the existing sign-in helper await asynchronous submission
  before checking its destination, retaining all original route assertions.

## Verification commands

```powershell
# Django: focused management, URL security and removal regressions
.\venv\Scripts\python.exe -m pytest tests/test_kb_management.py tests/test_kb02_links.py tests/test_kb07_remove.py -q
# Same full non-embedding coverage command as CI
.\venv\Scripts\python.exe -m pytest -m "not embedding" --cov=knowledgebase --cov-report=term-missing

# Spring: management HTTP, role and forwarding tests
.\mvnw.cmd '-Dtest=*KnowledgeBase*Test' test
.\mvnw.cmd '-Dtest=PublicQueryEndpointTest' test

# Frontend
npx.cmd vitest run --config vite.config.js test/components/KnowledgeBaseManager.test.jsx test/services/knowledgeBaseService.test.js
npx.cmd eslint src/components/chatbot/KnowledgeBaseManager.jsx src/services/knowledgeBaseService.js
npm.cmd run build
```

The explicit Vite config selects the existing `test/` directory. On restricted
Windows test environments, use a fresh workspace-local `--basetemp` and disable
the pytest cache if the system temporary/cache directory is inaccessible.

Final verification checklist:

- Upload a valid PDF: 201/PENDING, persisted metadata, processed by the existing worker.
- Reject invalid, oversized PDFs and unsafe/non-allowlisted links.
- List both resource kinds, paginate and filter; inspect details without private paths.
- Require an authorized staff JWT; deny other roles and unauthenticated requests.
- Confirm removal before sending DELETE; check the resource leaves active listings.
- Verify removed resources cannot be retrieved or reactivated during ingestion.
- Verify patient chat and suggested questions still work independently of this screen.
- Read the actual test results below; no live production-resource mutation is required for these tests.

## Executed results

- Django focused management, URL-security and removal tests: **41 passed**.
- Full Django non-embedding coverage run: **413 passed, 1 skipped, 4 deselected**;
  knowledgebase coverage **91%**. This includes existing guardrails, clinic answers,
  logging, RAG, storage, FAISS deletion and in-flight removal tests.
- `manage.py makemigrations --check --dry-run`: **No changes detected**.
- Spring knowledge-base suites: **32 passed** initially; the expanded controller
  suite then passed **4 tests**, replacing its previous 3-test run (33 management
  tests verified across the runs). The real HTTP client tests cover all operations,
  explicit body lengths, actor/service authentication headers and upstream timeouts.
- Existing Spring public chatbot endpoint regression suite: **30 passed**.
  A further application-context smoke test passed with multipart limits loaded
  from the tracked shared YAML configuration.
- Frontend management/API/role-routing verification: **21 passed** in the final
  run, including the new authorized/denied page checks. Existing widget, navigation
  and RequireAuth suites also passed during broader verification.
- Earlier combined UI runs exposed timing-sensitive existing login assertions.
  The test helper now awaits completion of asynchronous sign-in before checking the
  destination. Original destination assertions remain; production login was not changed.
- Production frontend build, targeted ESLint, targeted Ruff and Postman JSON parsing
  passed. The build retains pre-existing bundle-size/dynamic-import warnings.
- No migration, dependency installation, or mutation of production knowledge
  resources was performed for these management tests. Their writes use the existing
  isolated chatbot test database and temporary storage directories.

The management interface is implemented and tested but was not manually exercised
with a real staff browser login. Restart the local servers to load the new routes,
use an existing authorized staff account, and run the ingestion worker to move new
uploads from PENDING to INDEXED/FAILED.
