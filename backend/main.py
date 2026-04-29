import os
import json
import asyncio
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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
print(f"DEBUG: api_key is '{api_key}'")
if not api_key:
    # Fallback for demo if key is missing (though in production it should be set)
    print("WARNING: GOOGLE_API_KEY not found in environment.")

genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-1.5-flash')

class PromptRequest(BaseModel):
    prompt: str

class PipelineStep(BaseModel):
    step: str
    status: str
    data: Optional[dict] = None

# --- Mock Data for Demo ---
MOCK_DESIGN = {
    "app_name": "SaaS Platform",
    "core_features": ["User Management", "Dashboard", "Analytics"],
    "entities": ["User", "Post", "Metric"],
    "user_roles": ["Admin", "Member"]
}

MOCK_SCHEMAS = {
    "ui_layout": { "pages": [{"name": "Home", "route": "/"}] },
    "api_endpoints": { "endpoints": [{"path": "/api/users", "method": "GET"}] },
    "db_schema": { "tables": [{"name": "users", "columns": ["id", "name"]}] }
}

MOCK_VALIDATION = { "status": "SUCCESS", "issues": [] }

MOCK_MODE = True # Toggle this for real LLM calls

async def safe_generate(func, *args, **kwargs):
    if MOCK_MODE or not api_key:
        await asyncio.sleep(1) # Simulate delay
        if func == "intent": return MOCK_DESIGN
        if func == "schemas": return MOCK_SCHEMAS
        if func == "validate": return MOCK_VALIDATION
    return await globals()[f"_{func}"](*args, **kwargs)

async def _intent(prompt: str):
    system_prompt = """
    You are an AI Architect. Parse the user's app idea into a high-level system design.
    Return ONLY a JSON object with:
    {
      "app_name": "string",
      "core_features": ["list"],
      "entities": ["list of data objects"],
      "user_roles": ["list"]
    }
    """
    response = model.generate_content(f"{system_prompt}\n\nUser Prompt: {prompt}", generation_config={"response_mime_type": "application/json"})
    return json.loads(response.text)

async def _schemas(design: dict, error_context: str = None):
    system_prompt = """
    You are a Full-Stack Compiler. Convert the system design into detailed UI, API, and DB schemas.
    Return ONLY a JSON object with:
    {
      "ui_layout": { "pages": [...] },
      "api_endpoints": { "endpoints": [...] },
      "db_schema": { "tables": [...] }
    }
    """
    if error_context:
        system_prompt += f"\n\nIMPORTANT: Previous schemas had errors. Please fix: {error_context}"
    
    response = model.generate_content(f"{system_prompt}\n\nDesign: {json.dumps(design)}", generation_config={"response_mime_type": "application/json"})
    return json.loads(response.text)

async def _validate(schemas: dict):
    system_prompt = """
    You are a System Validator. Audit the UI, API, and DB schemas for consistency.
    Check:
    1. Do UI components have corresponding API endpoints?
    2. Do API endpoints match DB tables?
    
    Return ONLY a JSON object with:
    {
      "status": "SUCCESS" or "ERROR",
      "issues": ["list of issues if ERROR"]
    }
    """
    response = model.generate_content(f"{system_prompt}\n\nSchemas: {json.dumps(schemas)}", generation_config={"response_mime_type": "application/json"})
    return json.loads(response.text)

# --- Endpoints ---

@app.post("/compile")
async def compile_app(request: PromptRequest):
    logs = []
    
    try:
        # Step 1: Architecting
        logs.append({"step": "Architecting Intent...", "status": "running"})
        design = await safe_generate("intent", request.prompt)
        logs.append({"step": "Architecting Intent...", "status": "completed", "data": design})
        
        # Step 2: Compiling Schemas
        logs.append({"step": "Compiling Schemas...", "status": "running"})
        schemas = await safe_generate("schemas", design)
        logs.append({"step": "Compiling Schemas...", "status": "completed", "data": schemas})
        
        # Step 3: Validating
        logs.append({"step": "Validating System Integrity...", "status": "running"})
        validation = await safe_generate("validate", schemas)
        
        if validation["status"] == "ERROR":
            logs.append({"step": "Repairing Mismatches...", "status": "running", "issues": validation["issues"]})
            # Smart Repair Attempt
            schemas = await safe_generate("schemas", design, error_context=str(validation["issues"]))
            logs.append({"step": "Repairing Mismatches...", "status": "completed", "data": schemas})
            
            # Final validation check
            logs.append({"step": "Final Validation Check...", "status": "running"})
            validation = await safe_generate("validate", schemas)
            logs.append({"step": "Final Validation Check...", "status": "completed", "data": validation})
        else:
            logs.append({"step": "Validating System Integrity...", "status": "completed", "data": validation})
            
        return {
            "success": True,
            "logs": logs,
            "final_schemas": schemas,
            "validation": validation
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "logs": logs
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
