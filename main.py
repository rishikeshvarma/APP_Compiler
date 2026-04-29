import os
import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from agents import SaaSCompiler

app = FastAPI(title="SaaS Compiler API")
compiler = SaaSCompiler()

class CompileRequest(BaseModel):
    prompt: str

@app.post("/compile")
async def compile_app(request: CompileRequest):
    try:
        # 1. Generate Design
        design = compiler.generate_design(request.prompt)
        
        # 2. Generate Schemas
        schemas = compiler.generate_schemas(design)
        
        # 3. Validate and Repair
        final_schemas, repair_count = compiler.validate_and_repair(schemas)
        
        # Save to output folder
        output_dir = "/home/rishi/Desktop/stuff/AI_Internship/project/output"
        os.makedirs(output_dir, exist_ok=True)
        
        with open(os.path.join(output_dir, "ui_layout.json"), "w") as f:
            json.dump(final_schemas["ui_layout"], f, indent=2)
            
        with open(os.path.join(output_dir, "api_endpoints.json"), "w") as f:
            json.dump(final_schemas["api_endpoints"], f, indent=2)
            
        with open(os.path.join(output_dir, "db_schema.sql"), "w") as f:
            f.write(final_schemas["db_schema"])
            
        return {
            "message": "Compilation successful",
            "repair_count": repair_count,
            "output_directory": output_dir,
            "schemas": final_schemas
        }
    except Exception as e:
        print(f"[Error] {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
