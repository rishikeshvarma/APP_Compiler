"""MOCK SERVER, NOT THE REAL PIPELINE.

Moved from backend/main.py. When no API key is set it streams canned schemas, and its
"validation" stage is a sleep with a hardcoded SUCCESS, so timings and results from this
server say nothing about the compiler. The real pipeline is agents.py (served by main.py
locally and api/index.py on Vercel); measure it with `python -m evals.runner`.
"""
import os
import json
import asyncio
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="AppCompiler Backend")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure Gemini
api_key = os.getenv("GOOGLE_API_KEY")
if api_key:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
else:
    model = None

class PromptRequest(BaseModel):
    prompt: str

# --- Mock Data for Demo ---
MOCK_DESIGN = "Architectural Intent: SaaS Platform with User Management, Dashboard, and Analytics."
MOCK_SCHEMAS = {
    "ui_layout": { "pages": [{"name": "Home", "route": "/"}] },
    "api_endpoints": { "endpoints": [{"path": "/api/users", "method": "GET"}] },
    "db_schema": "CREATE TABLE users (id SERIAL PRIMARY KEY, name TEXT);"
}
MOCK_MODE = False # Set to True for testing without API keys

async def compilation_stream(prompt: str):
    try:
        # Step 1: Architecting
        yield f"data: {json.dumps({'step': 'Architecting Intent...', 'status': 'running'})}\n\n"
        if MOCK_MODE or not model:
            await asyncio.sleep(1)
            design = MOCK_DESIGN
        else:
            system_prompt = "You are an AI Architect. Parse the user's app idea into a high-level system design spec in Markdown."
            response = await asyncio.to_thread(model.generate_content, f"{system_prompt}\n\nUser Prompt: {prompt}")
            design = response.text
        yield f"data: {json.dumps({'step': 'Architecting Intent...', 'status': 'completed', 'data': design})}\n\n"
        
        # Step 2: Compiling Schemas
        yield f"data: {json.dumps({'step': 'Compiling Schemas...', 'status': 'running'})}\n\n"
        if MOCK_MODE or not model:
            await asyncio.sleep(1)
            schemas = MOCK_SCHEMAS
        else:
            system_prompt = "You are a Full-Stack Compiler. Convert the design into UI (JSON), API (JSON), and DB (SQL) schemas."
            response = await asyncio.to_thread(model.generate_content, f"{system_prompt}\n\nDesign: {design}", generation_config={"response_mime_type": "application/json"})
            schemas = json.loads(response.text)
        yield f"data: {json.dumps({'step': 'Compiling Schemas...', 'status': 'completed', 'data': schemas, 'partial': True})}\n\n"
        
        # Step 3: Validating
        yield f"data: {json.dumps({'step': 'Validating System Integrity...', 'status': 'running'})}\n\n"
        await asyncio.sleep(1)
        yield f"data: {json.dumps({'step': 'Validating System Integrity...', 'status': 'completed', 'data': schemas, 'repair_status': 'SUCCESS'})}\n\n"
        
        yield f"data: {json.dumps({'success': True, 'final': True})}\n\n"
        
    except Exception as e:
        yield f"data: {json.dumps({'success': False, 'error': str(e)})}\n\n"

@app.post("/api/compile")
async def compile_app(request: PromptRequest):
    return StreamingResponse(compilation_stream(request.prompt), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
