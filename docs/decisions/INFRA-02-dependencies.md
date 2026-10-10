# INFRA-02 — Dependency and embedding-model decisions

| | |
|---|---|
| **Ticket** | INFRA-02 — Install and Pin Chatbot Dependencies (issue #3) |
| **Parent** | DDP-35 — Stage 1: Environment Setup |
| **Author** | `Sweeskaran` |
| **Date** | `<2026-10-10>` |
| **Status** | Draft for peer review |
| **Branch** | `feature/INFRA-02-pin-dependencies` → `develop` |

> **Before committing:** every `<...>` placeholder below must be replaced with a real value from your own
> output (commands are given in each section). Delete this box when done.
>
> | Fill in | Where to get it |
> |---|---|
> | mysqlclient, gunicorn, ruff versions | `Select-String -Path requirements.in,requirements-dev.in -Pattern "mysqlclient\|gunicorn\|ruff"` |
> | Model revision hash | `model_info("sentence-transformers/LaBSE").sha` (see §5) |
> | Model license and size | the model page on Hugging Face, and the size of the cache volume |
> | Image size | `docker images onecare-chat` |
> | Six cosine values and `min_cosine` | the `PAIR SIMILARITIES` line printed by the embedding test |
> | Audit result | output of the `pip-audit` command in §8 |

---

## 1. Summary of decisions

| # | Decision | Reason |
|---|---|---|
| D1 | Python is pinned to **3.11.9** (`.python-version`, `Dockerfile`, CI). | The lock file is only valid for one Python version; the INFRA-01 Dockerfile already uses it. |
| D2 | Django is pinned to **5.2.18** (5.2 LTS series), not 6.x. | Django 6.x requires Python ≥ 3.12 (see §2). |
| D3 | Dependencies are declared in `requirements.in` / `requirements-dev.in` and **locked with `pip-compile` inside Docker** into `requirements.txt` / `requirements-dev.txt`. | Reproducible, Linux-correct lock regardless of the developer's OS. |
| D4 | Runtime and dev tools are kept in **separate** files. | The production image must not contain test, lint or audit tooling. |
| D5 | **CPU-only PyTorch** (`--extra-index-url https://download.pytorch.org/whl/cpu`). | The chatbot only embeds text; no GPU is needed and the CPU wheel is far smaller. |
| D6 | Vector library: **FAISS** (`faiss-cpu`). | See §4. |
| D7 | Embedding model: **LaBSE**, pinned to a fixed revision. | One vector space for Tamil and English (see §5). |
| D8 | No LLM SDK, no web-scraping libraries in this ticket. | Out of scope per the ticket (see §9). |

## 2. Python and Django version decision

**What happened.** The first `docker build` failed with:

```
ERROR: Could not find a version that satisfies the requirement Django==6.1.1
ERROR: Ignored the following versions that require a different python version: 6.1 Requires-Python >=3.12 ...
```

`Django==6.1.1` had been written into `requirements.in` after looking up "latest" versions in a local Python 3.13
environment. The Docker image uses Python 3.11.9, where the newest installable Django is 5.2.x.

| Option | Description | Outcome |
|---|---|---|
| **A (chosen)** | Keep Python 3.11.9 and use **Django 5.2.18** (LTS). | One-line change; consistent with INFRA-01 `Dockerfile` and CI. |
| B | Move everything to Python 3.12+ and keep Django 6.x. | Requires changing `.python-version`, `Dockerfile`, lock command and CI, and agreement from the team. Not chosen for this ticket. |

**Rule adopted:** versions are looked up **inside the target Python image**, never on a developer's local Python:

```powershell
docker run --rm python:3.11.9-slim pip index versions <package>
```

## 3. Direct dependencies

Runtime (`requirements.in`):

| Package | Pinned version | Purpose | Why chosen | Alternatives considered |
|---|---|---|---|---|
| Django | 5.2.18 | Web framework (from INFRA-01) | LTS series that supports Python 3.11 | Django 6.x (needs Python ≥ 3.12) |
| djangorestframework | `<verify in requirements.in>` | REST API (from INFRA-01) | Already in use | — |
| mysqlclient | `<version>` | MySQL driver (from INFRA-01) | Already in use | PyMySQL |
| gunicorn | `<version>` | Production WSGI server (from INFRA-01) | Already in use | uvicorn |
| pdfplumber | 0.11.10 (verify) | PDF text extraction (FR047) | Reliable text/layout extraction | pypdf |
| sentence-transformers | 6.1.0 | Loads the embedding model | One API for LaBSE and similar models | Raw `transformers` |
| langdetect | 1.0.9 | English/Tamil language detection | Pure Python, no model file | fastText |
| faiss-cpu | 1.15.1 | Vector similarity search | See §4 | Chroma |

Transitive packages of note (pinned automatically in `requirements.txt`): `torch==2.14.1+cpu`, `transformers`,
`numpy`, `pdfminer.six`.

Dev only (`requirements-dev.in`):

| Package | Pinned version | Purpose |
|---|---|---|
| pytest | 9.1.1 | Test runner |
| pytest-django | 4.14.0 | Django integration for pytest |
| ruff | `<version>` | Linting |
| pip-audit | 2.10.1 | Vulnerability scanning (AC4) |
| pip-tools | 7.4.1 | `pip-compile` to generate the lock files |

## 4. FAISS vs Chroma

| | FAISS (`faiss-cpu`) | Chroma |
|---|---|---|
| Size of dependency tree | Small | Larger |
| Search | Exact (flat index), sufficient for a small curated knowledge base | Approximate by default |
| Metadata filtering (`active`, language) | Not built in — done in our own code | Built in |
| Persistence | Index file + JSON on disk | Own storage layer |

**Decision: FAISS.** The knowledge base is small and curated by doctors, so exact search is cheap and the lighter
dependency set is preferred. Trade-off accepted: the `active` and language filters are implemented in
`vectorstore/store.py`. If the knowledge base grows to hundreds of thousands of chunks, or the service is run on
several nodes, this decision should be revisited.

## 5. Embedding model

| Item | Value |
|---|---|
| Model | `sentence-transformers/LaBSE` |
| Pinned revision | `<commit hash from model_info(...).sha>` (stored in `vectorstore/model_config.py`) |
| License | `<confirm on the model page>` |
| Size | `<measured size of the downloaded weights>` |
| Languages | Covers both English and Tamil in one shared vector space |
| Vector size | 768 |
| Use in the pipeline | Embed document chunks at ingestion (KB-05) and embed patient queries at retrieval (CHAT-04) |

**Weights delivery.** Weights are **not baked into the image**. They are loaded from a cache volume
(`~/.cache/huggingface`): a Docker volume `hf_cache` for local runs and `actions/cache` keyed on
`vectorstore/model_config.py` in CI. This keeps the image small and the weights download only happens when the
pinned revision changes.

| Image | Size |
|---|---|
| `onecare-chat` (runtime lock, no model weights) | `<value from docker images>` |

If production later needs offline start-up, weights can be baked into the image; the image size would then grow by
the model size above.

## 6. Multilingual smoke test (AC5)

Test: `tests/test_embedding_compat.py` (marker `embedding`), data: `tests/fixtures/embedding_pairs.json`
(6 Tamil/English clinic-information pairs: opening hours, appointment booking, no medical advice, documents to
bring, cancellation, emergency).

| Check | Result |
|---|---|
| Both languages embed in one 768-dimension space, no NaN values | `<pass/fail>` |
| Each Tamil sentence is closest to its own English equivalent | `<pass/fail>` |
| Every pair meets the minimum cosine similarity | `<pass/fail>` |

| Pair | Cosine similarity |
|---|---|
| 1 Opening hours | `<value>` |
| 2 Appointment booking | `<value>` |
| 3 No medical advice | `<value>` |
| 4 Documents to bring | `<value>` |
| 5 Cancellation | `<value>` |
| 6 Emergency | `<value>` |

- **Lowest observed pair similarity:** `<value>`
- **Recorded minimum (`min_cosine`):** `<value, set slightly below the lowest observed>`

**Scope.** This test verifies cross-lingual **compatibility only**. It does not measure production retrieval
quality; that is covered by TEST-02 and TEST-03.

**Review.** The Tamil sentences were reviewed by `<name>` on `<date>` / **are pending review by a Tamil speaker**
*(delete one)*.

**Where it was run.** In the locked Linux environment (Python 3.11.9 with `requirements-dev.txt`) via Docker,
the same environment CI uses. See §10 for why it was not run in a local Python.

## 7. Reproducibility

- Python version pinned in `.python-version`, `Dockerfile` and `ci.yml` (all 3.11.9).
- `requirements.txt` and `requirements-dev.txt` are **generated**, never edited by hand. To change a dependency:
  edit the `.in` file, then re-run `pip-compile` in the Docker helper image.
- `scripts/check_pins.py` fails (locally and in CI) if any entry in a requirements file is not pinned with `==`,
  and reports the package name and the invalid specifier.
- The `Dockerfile` copies **only** `requirements.txt`, installs it, then runs `pip check` and
  `scripts/check_installed.py` to prove the installed versions equal the lock.
- No dependency is installed from the host; local development uses a virtual environment or Docker.

## 8. Vulnerability scan (AC4)

Command (CI and local):

```
pip-audit -r requirements.txt --no-deps --disable-pip
```

**Result:** `<choose one>`

- No known vulnerabilities found.
- Findings and actions: `<package, vulnerability ID, fixed by upgrading to X / accepted as an exception>`.
  Exceptions are listed in `docs/decisions/security-exceptions.md`, each with a reason, reviewer and review date.

**Note on the CPU PyTorch build.** The version string `2.14.1+cpu` is not a plain PyPI version, so `pip-audit` may
skip it with a warning. `<state whether this occurred>`. It is not a vulnerability finding.

## 9. Deliberately not installed

| Package / area | Reason |
|---|---|
| LLM provider SDK (e.g. Gemini) | Not installed until a decision note is approved covering provider, data sent, privacy (CON003), and how BR009/BR010 are enforced. |
| `trafilatura`, `beautifulsoup4` | Removed by the ticket — no web sources (FR046/FR047). |
| `celery`, `redis`, `gTTS` | Not required by this ticket's architecture; to be proposed in the ticket that needs them. |

## 10. Issues found during implementation

| Issue | Cause | Resolution / rule |
|---|---|---|
| `Django==6.1.1` could not be installed in Docker. | Versions were looked up with a local Python 3.13; Django 6.x needs Python ≥ 3.12. | Chose Django 5.2.18 (§2). Look up versions inside the target Python image. |
| `check_pins.py` rejected `asgiref==3.12.1`. | A byte-order mark (BOM) at the start of a Windows-saved file; the file was also not a real `pip-compile` output. | Scripts read files with `utf-8-sig`; lock files are only produced by `pip-compile`. |
| `pip-compile` failed with `HashMismatch`. | Corrupted download on the developer's network (the received hash differed on every attempt). | Re-run; use a different network or pause HTTPS scanning if it persists. Not a project defect. |
| `ResolutionImpossible` for pytest. | `pytest` was listed in both `requirements.in` (9.1.1) and `requirements-dev.in` (typo 9.11), and the dev file includes the runtime file. | Dev tools live **only** in `requirements-dev.in`; runtime lock regenerated without them. |
| Embedding test crashed on `import sentence_transformers` (`AuxRequest` import error). | Global Python 3.13 had mismatched `transformers` and `torch`. | Run tests in the locked environment (Docker / CI), not the global Python. |
| "No space left on device" during a local install. | C: drive was full; PyTorch is large. | Resolve versions without installing (`pip index versions` in Docker); keep Docker storage on a drive with free space. |

## 11. Language detection note

`langdetect` can return different results between runs on short text unless its seed is fixed. When language
detection is implemented in CHAT-01, set `DetectorFactory.seed = 0`. Tamil text should additionally be detected by
Unicode script range, because `langdetect` is unreliable on very short Tamil strings. *(Not part of this PR; recorded
here as a follow-up.)*

## 12. Follow-ups and limitations

- Tamil test sentences need review by a native speaker if not yet done (§6).
- Lock files do not use `--generate-hashes`. This can be added later for stronger supply-chain protection; it
  requires adjusting `scripts/check_pins.py`.
- Revisit FAISS vs Chroma if the knowledge base or deployment topology grows (§4).
- INFRA-03 will add the MySQL configuration and `KnowledgeDocument` model; no changes to this lock are expected
  beyond the database driver already included.