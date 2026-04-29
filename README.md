# AppCompiler: A Self-Healing SaaS Architecture Engine

[![Audit Status](https://img.shields.io/badge/Audit-PASS-emerald)](#the-judge-audit-results)
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

## 📊 "The Judge" Audit Results

Our system was recently challenged with a **HIPAA-compliant Healthcare CRM** audit.

| Metric | Result | Note |
| :--- | :--- | :--- |
| **Multi-Stage Separation** | ✅ 100% | Distinct Architecting, Compiling, and Validating stages. |
| **Cross-Layer Consistency** | ✅ 100% | All UI components mapped to valid API/DB entities. |
| **Repair Engine Effectiveness** | ✅ 100% | Identified and fixed a missing `appointments` entity in pass 1. |
| **Execution Awareness** | ✅ PASS | Generated Postgres Triggers and Immutable Audit Logs. |
| **Deterministic Reliability** | ⚠️ 85% | Structural consistency is high; naming varies slightly per run. |

---

## 🛠️ Setup & Deployment

## Project Structure
```text
├── backend/            # FastAPI Implementation
├── frontend/           # Vite + React Dashboard
├── blueprints/         # High-level design artifacts
├── schemas/            # Generated UI/API/DB outputs
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

### Vercel Monorepo Deployment
AppCompiler is optimized for Vercel Serverless Functions:
*   **Root Directory**: `./`
*   **Build Command**: `cd frontend && npm install && npm run build`
*   *Note: Ensure `maxDuration: 300` is set in Project Settings to allow for complex AI repair cycles.*

---
*Developed by **K. Sri Rishikesh varma**. High-fidelity, self-healing architecture.*
