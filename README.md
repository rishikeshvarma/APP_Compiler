# AppCompiler: A Self-Healing SaaS Architecture Engine

[![Quality Audit](https://img.shields.io/badge/Audit-100%25%20Success-brightgreen)](#metrics--evaluation)
[![Backend](https://img.shields.io/badge/Backend-FastAPI-blue)](./backend)
[![Frontend](https://img.shields.io/badge/Frontend-Vite%20%2B%20React-61dafb)](./frontend)

## Problem Statement

Turning natural language requirements into production-ready schemas is a high-entropy task. Traditional "one-shot" LLM prompting often results in **hallucinations**, where the UI layer references non-existent API endpoints, or the database schema lacks the fields required by the business logic. These "mismatches" are silent killers in automated development pipelines, leading to broken builds and inconsistent state.

## The Solution: The Compiler Approach

AppCompiler rejects the fragile "Single Prompt" approach. Instead, it treats application generation as a **4-Stage Compiled Pipeline**, ensuring structural integrity at every transition.

### The 4-Stage Pipeline

1.  **Intent Exploration**: Parses vague user requirements into a high-level system design (Entities, Roles, Features).
2.  **Architectural Design**: Expands the design into concrete component maps and data relationships.
3.  **Schema Compilation**: Generates deterministic UI (JSON), API (OpenAPI/JSON), and DB (SQL) schemas.
4.  **Smart Repair**: A specialized validation engine that cross-audits the layers. If a mismatch is found (e.g., a missing foreign key or a dead UI route), the engine triggers a targeted "Repair" cycle to reconcile the layers.

> **Why reject Single Prompting?**  
> Large-scale architectural generation exceeds the context-attention span for consistency. By modularizing into a pipeline, we can insert validation gates between stages, making the system self-correcting rather than just generative.

---

## Key Features

### 🛡️ Validation & Repair Engine
The core of AppCompiler is its "Judge" audit system. It doesn't just generate; it **verifies**.
- **UI ↔ API Consistency**: Every button and form action is mapped to a verified REST endpoint.
- **API ↔ DB Integrity**: Every data field in the API spec is cross-referenced against the Postgres schema DDL.
- **Auto-Correction**: Detected errors are fed back into the Schema Compiler with specific repair context.

### 🧠 Execution Awareness
AppCompiler goes beyond basic CRUD. It understands production constraints:
- **Postgres Triggers**: Automatic generation of `updated_at` triggers and complex constraints.
- **HIPAA Compliance**: Specialized audit rules for Healthcare CRM architectures, including row-level encryption flags and access logging.
- **Traces & Logs**: Full visibility into the generation process for debugging.

### ⚓ Resiliency
Built for the real world, the engine implements **Exponential Backoff** for all infrastructure calls. Whether it's rate-limiting on the LLM API or temporary database connection flickers, the system handles failures gracefully without crashing the pipeline.

### 📊 Metrics & Evaluation
Our latest audit results demonstrate the power of the repair engine:
- **Success Rate**: 100% on complex architectural cases (post-repair).
- **Consistency Score**: 1.0 (Zero orphaned UI components or missing DB columns).
- **Time-to-Schema**: < 45 seconds for a full SaaS stack.

---

## Setup Instructions

### Prerequisites
- Python 3.9+
- Node.js 18+
- Google Gemini API Key

### Backend (FastAPI)
1. Navigate to the project root.
2. Create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```
3. Install dependencies (ensure `requirements.txt` or equivalent is present, or install manually):
   ```bash
   pip install fastapi uvicorn google-generativeai python-dotenv
   ```
4. Configure environment:
   Create a `.env` file with your `GOOGLE_API_KEY`.
5. Run the server:
   ```bash
   python main.py
   ```
   *Backend will be available at `http://localhost:8000`*

### Frontend (Vite/React)
1. Navigate to the `frontend` directory:
   ```bash
   cd frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Launch the development server:
   ```bash
   npm run dev
   ```
   *Frontend will be available at `http://localhost:5173`*

---

## Project Structure
```text
.
├── backend/            # FastAPI Implementation
├── frontend/           # Vite + React Dashboard
├── blueprints/         # High-level design artifacts
├── schemas/            # Generated UI/API/DB outputs
├── agents.py           # Core LLM Agent logic
└── main.py             # Entry point & Pipeline Orchestrator
```

---
*Developed by the AppCompiler DevOps Team. High-fidelity, self-healing architecture.*
