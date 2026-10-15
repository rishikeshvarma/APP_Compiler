# AppCompiler: A Self-Healing SaaS Architecture Engine

[![evals](https://github.com/rishikeshvarma/APP_Compiler/actions/workflows/evals.yml/badge.svg)](https://github.com/rishikeshvarma/APP_Compiler/actions)
[![Model](https://img.shields.io/badge/AI%20Engine-Gemini%203%20Flash-blue)](https://deepmind.google/technologies/gemini/)
[![Deployment](https://img.shields.io/badge/Deployment-Vercel%20Monorepo-black)](./vercel.json)

## Problem Statement

Turning natural language requirements into production-ready schemas is a high-entropy task. Traditional "one-shot" LLM prompting often results in **hallucinations**, where the UI layer references non-existent API endpoints, or the database schema lacks the fields required by the business logic. These "mismatches" are silent killers in automated development pipelines, leading to broken builds and inconsistent state.

## The Solution: The Compiler Approach

AppCompiler rejects the fragile "Single Prompt" approach. Instead, it utilizes a **4-Stage Compiled Pipeline** that streams partial state updates to the UI in real-time using **Server-Sent Events (SSE)**.

1.  **Architecting Intent**: Parses requirements into a high-level Design Spec (Entities, Roles, RBAC).
2.  **Schema Compilation**: Translates design into UI Layouts (JSON), API Endpoints (JSON), and DB DDL (SQL).
3.  **Smart Validation**: A "Judge" agent audits the schemas for orphans (e.g., a UI button pointing to a missing API path).
4.  **Self-Repair**: If inconsistencies are found, the engine triggers a repair cycle, reconciling all layers before final output.

---

## 🚀 Key Features

### 📡 Real-Time Partial Updates
The UI is built on a streaming architecture. As soon as Stage 1 is complete, the **Architectural Intent** is rendered in the dashboard while Stage 2 compiles in the background. No more waiting for "all or nothing" responses.

### 🛡️ Execution Awareness & Resiliency
*   **Production-Ready SQL**: Generates Postgres Triggers, Immutable Audit Rules (`INSTEAD NOTHING`), and UUID-based primary keys.
*   **HIPAA & Compliance**: Built-in awareness for sensitive architectures (Encryption flags, Access logging).
*   **Infrastructure Resiliency**: Implements **Exponential Backoff** to handle rate limits and API flickers gracefully.

### 🎨 Premium UI Dashboard
A high-fidelity React dashboard featuring:
*   **Glassmorphism Layout**: A symmetrical 50/50 workspace for controls and output.
*   **Sequential JSON Viewers**: Tabs that update progressively as schemas are validated.
*   **Success Modal**: A summary popup providing an artifact count and repair status upon completion.

---

## 🧪 Evals & Regression Tests

An eval harness (`evals/`) grades compiled output with **deterministic checks first** and an LLM-as-judge second, traces every pipeline step (latency, tokens, error class), and gates changes against a committed baseline. Infrastructure errors such as quota limits are reported separately and never counted as model failures.

Measured on the recorded HIPAA healthcare output (`evals/recorded/healthcare-hipaa.json`):

| Check | Result |
| :--- | :--- |
| UI → API endpoint consistency (exact match, path params normalized) | ✅ pass |
| Every API resource has a backing table | ✅ pass |
| Foreign keys point at existing tables, no duplicate tables | ✅ pass |
| Audit-log table present and protected from UPDATE/DELETE | ✅ pass |
| A UI component reads a POST-only endpoint | ⚠️ warning |
| `/doctor/*` and `/ai/*` paths cannot be mapped to a table by name | ⚠️ warning |

Limits: only one output is recorded so far (the other 12 dataset cases are skipped until recorded with `--live --record`), and the LLM judge has not yet been calibrated against human labels.

```bash
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q                                                 # unit + regression tests, no API key
python -m evals.runner --replay evals/recorded --no-judge           # re-grade recorded outputs, gate on baseline
GOOGLE_API_KEY=... python -m evals.runner --live --record evals/recorded
```

### Bugs the harness found (each has a regression test)
1. The validator never checked UI→API when `data_endpoint` was top-level, so the self-repair check was skipped for generated schemas.
2. Prefix matching let `/api/v1/leads` pass when only `/api/v1/leads/hot` existed.
3. Quota errors were scored as model failures (a committed run showed 0/10 purely from a 429).
4. A per-day quota was retried with backoff for hours although it cannot recover.

See [`evals/README.md`](evals/README.md) for the design.

---

## 🛠️ Setup & Deployment

## Project Structure
```text
├── frontend/           # Vite + React Dashboard
├── blueprints/         # High-level design artifacts
├── schemas/            # Generated UI/API/DB outputs
├── evals/              # Eval harness: checks, judge, tracing, dataset, runner
├── tests/              # Unit + regression tests
├── examples/           # Mock server (not the real pipeline)
├── agents.py           # Core LLM Agent logic
└── main.py             # Entry point & Pipeline Orchestrator
```

### Local Development
1.  **Configure Environment**: Add `GOOGLE_API_KEY` to your `.env` file.
2.  **Start Backend**:
    ```bash
    python main.py  # Runs on http://localhost:8001
    ```
3.  **Start Frontend**:
    ```bash
    cd frontend && npm run dev  # Runs on http://localhost:5173
    ```
4.  **Run Tests**:
    ```bash
    pip install -r requirements-dev.txt && python -m pytest -q
    ```

### Vercel Monorepo Deployment
AppCompiler is optimized for Vercel Serverless Functions:
*   **Root Directory**: `./`
*   **Build Command**: `cd frontend && npm install && npm run build`
*   *Note: Ensure `maxDuration: 300` is set in Project Settings to allow for complex AI repair cycles.*

---
*Developed by **K. Sri Rishikesh varma**. High-fidelity, self-healing architecture.*
