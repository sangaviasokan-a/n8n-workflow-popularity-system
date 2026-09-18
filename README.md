# n8n Workflow Popularity Intelligence System

A production-oriented FastAPI + PostgreSQL + n8n system that discovers, validates, normalizes, deduplicates, scores, stores, and exposes popular n8n workflow evidence from **YouTube, n8n Community Forum, and Google Trends**.

The system separates **Popularity Score** from **Confidence Score**, stores historical metric snapshots, supports US/India Google Trends evidence, and exposes REST APIs for downstream applications and n8n automation.

> **Security:** API keys, database URLs, passwords, and other secrets are intentionally excluded from this submission package. Configure them locally or in the hosting platform's environment variables.

---

## 1. What the project does

```text
n8n Scheduler
     |
     +--> YouTube collection
     |
     +--> n8n Forum collection
     |
     +--> Google Trends collection
              |
              v
        Validation
              |
              v
    Normalization + Matching
              |
              v
        Deduplication
              |
              v
      Popularity Scoring
              |
              v
      Confidence Scoring
              |
              v
        PostgreSQL
              |
              v
          FastAPI
              |
              v
       REST JSON API
```

### Main capabilities

- Multi-source workflow discovery
- YouTube workflow/video evidence
- n8n Community Forum topic evidence
- Google Trends evidence for **US** and **IN**
- Input validation and invalid-record rejection
- Canonical workflow normalization
- Cross-platform workflow matching
- Source-level deduplication
- Popularity and confidence scoring
- Historical metric snapshots
- Pagination and platform/country filtering
- Graceful source failure and retry handling
- Structured application logging
- n8n daily and weekly orchestration
- PostgreSQL persistence
- FastAPI REST interface
- Automated unit/integration tests

The assignment requires at least 50 evidence-backed workflows. The local validation database previously contained **831 workflows**.

---

## 2. Technology stack

- Python 3.12+
- FastAPI
- Uvicorn
- Pydantic / pydantic-settings
- SQLAlchemy 2
- PostgreSQL
- psycopg 3
- httpx
- tenacity
- pytrends
- pytest
- pytest-asyncio
- n8n

Docker/WSL is **not required for local development**. PostgreSQL and n8n can run natively on Windows.

---

## 3. Project structure

```text
n8n-popularity-system/
├── app/
│   ├── api/
│   │   ├── collection.py
│   │   ├── health.py
│   │   └── workflows.py
│   ├── collectors/
│   │   ├── base.py
│   │   ├── forum.py
│   │   ├── google_trends.py
│   │   ├── queries.py
│   │   ├── trends.py
│   │   └── youtube.py
│   ├── database/
│   │   ├── database.py
│   │   └── repository.py
│   ├── models/
│   │   ├── metric.py
│   │   ├── source.py
│   │   └── workflow.py
│   ├── processors/
│   │   ├── deduplicator.py
│   │   ├── normalizer.py
│   │   ├── scorer.py
│   │   ├── validator.py
│   │   └── workflow_matcher.py
│   ├── schemas/
│   │   └── workflow.py
│   ├── services/
│   │   └── collector_orchestrator.py
│   ├── config.py
│   └── main.py
├── data/
│   └── sample_workflows.json
├── jobs/
│   ├── collect.py
│   ├── collect_forum.py
│   ├── collect_google.py
│   ├── collect_youtube.py
│   └── init_db.py
├── n8n/
│   └── popularity_pipeline.json
├── scripts/
│   ├── reconcile_workflows.py
│   ├── test_forum.py
│   ├── test_google_trends.py
│   └── test_youtube.py
├── tests/
├── .env.example
├── .gitignore
├── pytest.ini
├── requirements.txt
└── README.md
```

---

## 4. Windows setup

### Requirements

Install:

1. Python 3.12 or newer
2. PostgreSQL
3. Node.js
4. n8n

Verify:

```powershell
python --version
node --version
npm --version
n8n --version
```

Create the virtual environment:

```powershell
cd C:\Users\sriva\projects\n8n-popularity-system
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

---

## 5. PostgreSQL configuration

Create a PostgreSQL database, for example:

```text
Database: n8n_popularity
User: postgres
Host: localhost
Port: 5432
```

Copy the environment template:

```powershell
Copy-Item .env.example .env
```

Edit `.env`:

```env
APP_NAME=n8n Workflow Popularity Intelligence System
APP_ENV=development
DEBUG=true

DATABASE_URL=postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/n8n_popularity
YOUTUBE_API_KEY=YOUR_YOUTUBE_DATA_API_V3_KEY

API_HOST=0.0.0.0
API_PORT=8000
CORS_ORIGINS=http://localhost:3000,http://localhost:5678
```

**Never commit `.env`.**

The repository is configured to ignore `.env`, `.venv`, caches, and generated Python files.

---

## 6. Initialize the database

```powershell
python -m jobs.init_db
```

The application also creates missing tables during FastAPI startup.

To reconcile an existing database after upgrading the workflow-matching logic:

```powershell
python -m scripts.reconcile_workflows
```

---

## 7. Run FastAPI

```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Local API:

```text
http://127.0.0.1:8000
```

Swagger documentation:

```text
http://127.0.0.1:8000/docs
```

Health check:

```powershell
curl.exe http://127.0.0.1:8000/health
```

Expected:

```json
{
  "status": "healthy",
  "database": "connected"
}
```

---

## 8. REST API

### Health

```text
GET /health
```

### Root

```text
GET /
```

### Workflows

```text
GET /workflows
GET /workflows/{id}
GET /workflows/{id}/history
GET /workflows/top
```

Supported filters include pagination, platform, and country where applicable.

Examples:

```text
/workflows?page=1&page_size=20
/workflows?platform=youtube
/workflows?country=US
/workflows?country=IN
/workflows/top
/workflows/55
/workflows/55/history
```

### Platform evidence

```text
GET /workflows/youtube
GET /workflows/forum
GET /workflows/google
```

### Collection endpoints

The collection API exposes separate platform endpoints so n8n can orchestrate the sources independently:

```text
POST /collect/youtube
POST /collect/forum
POST /collect/google
POST /collect/run
```

`/collect/run` is retained for compatibility. **The n8n workflow uses the three platform-specific endpoints instead of the monolithic endpoint.**

---

## 9. Collection pipeline

### YouTube

The YouTube collector:

1. Searches multiple n8n workflow queries.
2. Deduplicates video IDs.
3. Retrieves video statistics in batches.
4. Validates views/likes/comments.
5. Calculates engagement ratios.
6. Normalizes workflow titles.
7. Stores source evidence.
8. Stores a historical metric snapshot.

YouTube API limits are respected by batching video IDs.

### n8n Forum

The Forum collector:

1. Searches multiple workflow-related queries.
2. Reads forum topic metadata.
3. Extracts views, replies, likes, and contributors when available.
4. Validates metrics.
5. Normalizes titles.
6. Deduplicates topic IDs.
7. Stores evidence and historical metrics.

Country is **not fabricated** for forum evidence.

### Google Trends

Google Trends collection supports:

- US
- IN

For each keyword/country combination it records:

- current search interest
- average interest
- maximum interest
- trend growth

Google Trends values are relative 0–100 measurements.

---

## 10. Validation

The validation layer rejects invalid evidence such as:

- missing required identifiers
- missing/invalid titles
- malformed URLs
- negative metrics
- impossible engagement relationships
- invalid country codes
- invalid source records

Validation happens before persistence.

---

## 11. Normalization and workflow matching

The system converts different source titles into a canonical workflow identity.

Examples:

```text
Build an n8n AI Agent
n8n AI Agent Tutorial
How to Build an AI Agent with n8n
```

can resolve to:

```text
n8n ai agent
```

Integration-specific workflows remain separate:

```text
n8n Gmail
n8n WhatsApp
n8n Google Sheets
```

The matcher uses conservative token/phrase similarity and integration-domain protection to avoid merging unrelated workflows.

---

## 12. Deduplication

Source-level uniqueness is enforced using:

```text
platform + source_id
```

The database has a unique constraint on this combination.

Examples:

```text
youtube + video_id
forum + topic_id
google + country:keyword
```

Repeated collection therefore reuses the same source and appends a new metric snapshot.

---

## 13. Popularity scoring

### Cross-platform weights

| Platform | Weight |
|---|---:|
| YouTube | 40% |
| Forum | 30% |
| Google | 30% |

If a platform is unavailable, the available platform weights are renormalized.

### YouTube

| Signal | Weight |
|---|---:|
| Views | 50% |
| Likes | 25% |
| Comments | 15% |
| Engagement | 10% |

### Forum

| Signal | Weight |
|---|---:|
| Views | 35% |
| Replies | 30% |
| Likes | 20% |
| Contributors | 15% |

### Google Trends

| Signal | Weight |
|---|---:|
| Search interest | 60% |
| Trend growth | 40% |

All scores are bounded to a 0–100 scale.

---

## 14. Confidence score

Popularity and confidence are intentionally separate.

Confidence uses:

- 40% evidence strength
- 30% platform coverage
- 30% data completeness

A workflow supported by multiple independent platforms can therefore have a different confidence level from a workflow supported by only one source.

---

## 15. Missing metric semantics

The project distinguishes:

```text
NULL = metric unavailable
0    = metric was genuinely zero
```

Unavailable metrics are preserved as `NULL` in PostgreSQL and JSON responses.

Derived ratios are also `NULL` when their required source metric is unavailable.

Popularity and confidence remain numeric calculated values.

---

## 16. Historical metrics

Every successful collection can append a new metric snapshot.

This supports:

```text
GET /workflows/{id}/history
```

Historical records include raw metrics, derived ratios, popularity score, confidence score, and Google Trends fields where applicable.

---

## 17. n8n automation

Import:

```text
n8n/popularity_pipeline.json
```

The workflow contains:

```text
Daily Trigger
    |
    v
Collect YouTube
    |
    v
Collect Forum
    |
    v
Collect Google Trends
```

and a separate weekly chain:

```text
Weekly Trigger
    |
    v
Weekly YouTube Collection
    |
    v
Weekly Forum Collection
    |
    v
Weekly Google Trends Collection
```

Default local endpoint:

```text
http://127.0.0.1:8000
```

### Important for hosted deployment

If n8n is running locally while FastAPI is hosted on Render, change each HTTP Request node from:

```text
http://127.0.0.1:8000/collect/...
```

to the public Render URL:

```text
https://YOUR-RENDER-SERVICE.onrender.com/collect/...
```

Do not use `localhost` from n8n to reach a remote Render service.

---

## 18. Reliability

The system includes:

- HTTP retries for transient failures
- timeout handling
- rate-limit handling
- source-level failure isolation
- validation before storage
- database transaction handling
- structured logging
- graceful Google Trends 429 handling
- historical snapshots
- database connection pre-ping

A failed source should not prevent the other collectors from being processed when using the complete orchestrator.

---

## 19. Hosted deployment

A simple low-cost architecture is:

```text
GitHub
   |
   v
Render
FastAPI
   |
   v
Neon PostgreSQL

Local n8n
   |
   v
Render HTTPS API
```

For deployment:

### Render build command

```text
pip install -r requirements.txt
```

### Render start command

```text
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### Render environment variables

```text
APP_NAME
APP_ENV
DEBUG
DATABASE_URL
YOUTUBE_API_KEY
API_HOST
API_PORT
CORS_ORIGINS
```

Do not place secrets in GitHub.

---

## 20. Testing

Run the full automated suite:

```powershell
pytest -q
```

The test suite covers:

- API endpoints
- validation
- collectors
- normalization
- workflow matching
- deduplication
- scoring
- repository persistence
- historical metrics
- country evidence
- missing metric semantics
- edge cases

External API smoke tests should be run separately with real credentials/connectivity.

---

## 21. External dependency verification

These checks require the user's own environment/API credentials and therefore should be run before submission.

### A. Python dependencies

```powershell
python -m pip install -r requirements.txt
python scripts/preflight.py
```

### B. PostgreSQL

Start PostgreSQL and verify:

```powershell
python -m jobs.init_db
curl.exe http://127.0.0.1:8000/health
```

Expected database status:

```text
connected
```

### C. YouTube API

Make sure `.env` contains a valid:

```text
YOUTUBE_API_KEY
```

Then:

```powershell
python scripts/test_youtube.py
```

### D. n8n Forum

```powershell
python scripts/test_forum.py
```

### E. Google Trends

```powershell
python scripts/test_google_trends.py
```

Google Trends is an external service and may occasionally return rate-limit or transient failures. A 429 response should be treated as a source availability issue, not as fabricated data.

### F. FastAPI collection smoke tests

With FastAPI running:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/collect/youtube"
curl.exe -X POST "http://127.0.0.1:8000/collect/forum"
curl.exe -X POST "http://127.0.0.1:8000/collect/google"
```

Check:

```text
/health
/workflows
/workflows/youtube
/workflows/forum
/workflows/google
/workflows/top
```

### G. n8n

Start:

```powershell
n8n
```

Open:

```text
http://localhost:5678
```

Import:

```text
n8n/popularity_pipeline.json
```

Execute the daily chain manually once and confirm all three HTTP Request nodes succeed.

---

## 22. Submission security checklist

Before uploading the final ZIP:

```powershell
git status
git check-ignore -v .env .venv .pytest_cache
```

Search for accidental credentials:

```powershell
Select-String -Path app\**\*.py,scripts\*.py,tests\*.py -Pattern "AIza|postgresql://|postgresql\+psycopg://|password=" -CaseSensitive:$false
```

Expected result should contain only intentional examples/test strings, never a real credential.

The final submission package should **not contain**:

```text
.env
.venv/
.git/
__pycache__/
.pytest_cache/
*.pyc
```

---

## 23. Known scoring limitation

Current platform normalization uses the current collection batch as its normalization baseline. Therefore, a popularity score can change when the composition of the batch changes even if an individual source's raw metrics remain unchanged.

For a future production version, introduce stable historical normalization baselines or versioned scoring calibration.

This limitation is documented rather than hidden.

---

## 24. Final submission checklist

- [x] FastAPI application
- [x] PostgreSQL persistence
- [x] YouTube collector
- [x] n8n Forum collector
- [x] Google Trends collector
- [x] Validation
- [x] Normalization
- [x] Cross-platform workflow matching
- [x] Deduplication
- [x] Popularity scoring
- [x] Confidence scoring
- [x] US/India evidence
- [x] Historical metrics
- [x] REST API
- [x] Pagination/filtering
- [x] Error handling
- [x] Logging
- [x] Tests
- [x] n8n daily/weekly workflow
- [x] Secrets excluded from submission
- [x] Native Windows setup documented
- [x] Hosted deployment documented

---

## 25. Important note

This repository is intentionally delivered **without live API credentials and database credentials**.

That is correct for a secure project submission.

Before running the collectors, the evaluator/developer must provide:

```text
DATABASE_URL
YOUTUBE_API_KEY
```

The n8n workflow does not contain secrets.

