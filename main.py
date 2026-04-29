import os
import json
import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from agents import SaaSCompiler

app = FastAPI(title="SaaS Compiler API")

# Add CORS Middleware for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

compiler = SaaSCompiler()

class CompileRequest(BaseModel):
    prompt: str

async def compilation_stream(prompt: str):
    try:
        # Step 1: Architecting Intent
        yield f"data: {json.dumps({'step': 'Architecting Intent...', 'status': 'running'})}\n\n"
        design = await asyncio.to_thread(compiler.generate_design, prompt)
        yield f"data: {json.dumps({'step': 'Architecting Intent...', 'status': 'completed', 'data': design})}\n\n"
        
        # Step 2: Compiling Schemas
        yield f"data: {json.dumps({'step': 'Compiling Schemas...', 'status': 'running'})}\n\n"
        schemas = await asyncio.to_thread(compiler.generate_schemas, design)
        yield f"data: {json.dumps({'step': 'Compiling Schemas...', 'status': 'completed', 'data': schemas, 'partial': True})}\n\n"
        
        # Step 3: Validating System Integrity
        yield f"data: {json.dumps({'step': 'Validating System Integrity...', 'status': 'running'})}\n\n"
        final_schemas, repair_count = await asyncio.to_thread(compiler.validate_and_repair, schemas)
        
        status = "SUCCESS" if repair_count == 0 else "REPAIRED"
        yield f"data: {json.dumps({'step': 'Validating System Integrity...', 'status': 'completed', 'data': final_schemas, 'repair_status': status})}\n\n"
        
        # Optional: Save to output folder
        try:
            output_dir = os.path.join(os.getcwd(), "output")
            os.makedirs(output_dir, exist_ok=True)
            with open(os.path.join(output_dir, "ui_layout.json"), "w") as f: json.dump(final_schemas["ui_layout"], f, indent=2)
            with open(os.path.join(output_dir, "api_endpoints.json"), "w") as f: json.dump(final_schemas["api_endpoints"], f, indent=2)
            with open(os.path.join(output_dir, "db_schema.sql"), "w") as f: f.write(final_schemas["db_schema"])
        except: pass

        yield f"data: {json.dumps({'success': True, 'final': True})}\n\n"
        
    except Exception as e:
        yield f"data: {json.dumps({'success': False, 'error': str(e)})}\n\n"

@app.post("/api/compile")
async def compile_app(request: CompileRequest):
    return StreamingResponse(compilation_stream(request.prompt), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
