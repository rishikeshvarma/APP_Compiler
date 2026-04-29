import os
import json
from fastapi import FastAPI, HTTPException
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

@app.post("/api/compile")
async def compile_app(request: CompileRequest):
    try:
        # 1. Generate Design
        design = compiler.generate_design(request.prompt)
        
        # 2. Generate Schemas
        schemas = compiler.generate_schemas(design)
        
        # 3. Validate and Repair
        final_schemas, repair_count = compiler.validate_and_repair(schemas)
        
        # Optional: Save to output folder (if writable)
        try:
            output_dir = os.path.join(os.getcwd(), "output")
            os.makedirs(output_dir, exist_ok=True)
            
            with open(os.path.join(output_dir, "ui_layout.json"), "w") as f:
                json.dump(final_schemas["ui_layout"], f, indent=2)
                
            with open(os.path.join(output_dir, "api_endpoints.json"), "w") as f:
                json.dump(final_schemas["api_endpoints"], f, indent=2)
                
            with open(os.path.join(output_dir, "db_schema.sql"), "w") as f:
                f.write(final_schemas["db_schema"])
        except Exception as e:
            print(f"[Warning] Could not write local files: {str(e)}")
            
        return {
            "message": "Compilation successful",
            "repair_count": repair_count,
            "schemas": final_schemas
        }
    except Exception as e:
        print(f"[Error] {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
