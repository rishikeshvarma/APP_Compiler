import os
import json
import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import sys

# Add root directory to sys.path so agents.py can be imported
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from agents import SaaSCompiler
except ImportError:
    # Fallback for different Vercel structure
    from ..agents import SaaSCompiler

app = FastAPI(title="SaaS Compiler API")
compiler = SaaSCompiler()

class CompileRequest(BaseModel):
    prompt: str

@app.get("/api/health")
async def health():
    return {"status": "healthy"}

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
        
        # Send final signal for the success popup
        yield f"data: {json.dumps({'success': True, 'final': True})}\n\n"
        
    except Exception as e:
        yield f"data: {json.dumps({'success': False, 'error': str(e)})}\n\n"

@app.post("/api/compile")
async def compile_app(request: CompileRequest):
    return StreamingResponse(compilation_stream(request.prompt), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
