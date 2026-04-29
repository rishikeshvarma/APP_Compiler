import os
import json
import time
import google.generativeai as genai
from typing import Dict, Any, List, Tuple
from functools import wraps
from dotenv import load_dotenv

# Load .env file from the current directory
load_dotenv()

def retry_with_backoff(retries=10, initial_delay=10):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None
            for i in range(retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if "429" in str(e) or "quota" in str(e).lower():
                        print(f"⚠️ Rate limit hit. Retrying in {delay}s... (Attempt {i+1}/{retries})")
                        time.sleep(delay)
                        delay *= 2  # Exponential backoff
                    else:
                        raise e
            print(f"❌ Max retries reached for {func.__name__}")
            raise last_exception
        return wrapper
    return decorator

class SaaSCompiler:
    def __init__(self, model_name: str = "gemini-3-flash-preview"):
        # Support both naming conventions
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("API Key not found. Please set GOOGLE_API_KEY or GEMINI_API_KEY in your .env file.")
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)

    @retry_with_backoff()
    def generate_design(self, prompt: str) -> str:
        """Calls Gemini to create a design spec."""
        print(f"[Agent] Generating design spec for: {prompt[:50]}...")
        system_prompt = """
        You are a Senior Systems Architect. Create a detailed Design Specification for a SaaS application.
        Include:
        1. Feature Map (UI views)
        2. Data Entities (properties and relationships)
        3. Auth Rules (RBAC and feature gating)
        
        Return the design in Markdown format.
        """
        response = self.model.generate_content(f"{system_prompt}\n\nUser Request: {prompt}")
        return response.text

    @retry_with_backoff()
    def generate_schemas(self, design: str) -> Dict[str, Any]:
        """Calls Gemini to produce JSON/SQL artifacts."""
        print("[Agent] Generating schemas from design spec...")
        system_prompt = """
        You are a Full-Stack Schema Compiler. Based on the design specification, generate three artifacts:
        1. ui_layout: A JSON object describing pages and components with data_endpoint fields. Format: {"pages": [...]}
        2. api_endpoints: A JSON object describing REST endpoints, methods, and validation. Format: {"endpoints": [...]}
        3. db_schema: Postgres DDL to support the application (String).
        
        Return the response as a valid JSON object with the following keys:
        {
          "ui_layout": <Object>,
          "api_endpoints": <Object>,
          "db_schema": <String>
        }
        Ensure that all data_endpoints in the UI exist in the API, and all API endpoints have corresponding DB tables.
        """
        response = self.model.generate_content(
            f"{system_prompt}\n\nDesign Spec:\n{design}",
            generation_config={"response_mime_type": "application/json"}
        )
        try:
            data = json.loads(response.text)
            if not isinstance(data, dict):
                raise ValueError("Response is not a JSON object")
            return data
        except Exception as e:
            print(f"[Error] Failed to parse schemas: {str(e)}")
            raise

    @retry_with_backoff()
    def validate_and_repair(self, schemas: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
        """Checks for mismatches and repairs them using Gemini."""
        print("[Agent] Validating system integrity...")
        
        if not isinstance(schemas, dict):
            print(f"[Error] schemas is not a dict: {type(schemas)}")
            return schemas, 0

        ui = schemas.get("ui_layout", {})
        api = schemas.get("api_endpoints", {})
        db = schemas.get("db_schema", "")
        
        # Ensure ui and api are dicts
        if isinstance(ui, list): ui = {"pages": ui}
        if isinstance(api, list): api = {"endpoints": api}
        
        issues = []
        
        # 1. Check UI -> API mapping
        api_paths = set()
        if isinstance(api, dict):
            endpoints = api.get("endpoints", [])
            if isinstance(endpoints, list):
                for e in endpoints:
                    if isinstance(e, dict):
                        api_paths.add(e.get("path"))

        if isinstance(ui, dict):
            for page in ui.get("pages", []):
                if isinstance(page, dict):
                    for comp in page.get("components", []):
                        if isinstance(comp, dict):
                            endpoint = comp.get("props", {}).get("data_endpoint")
                            if endpoint:
                                clean_endpoint = endpoint.split(":")[0].rstrip("/")
                                if not any(p.startswith(clean_endpoint) for p in api_paths if p):
                                    issues.append(f"UI component '{comp.get('component')}' references missing API path: {endpoint}")

        # 2. Check API -> DB mapping (Basic table existence check)
        if isinstance(api, dict):
            endpoints = api.get("endpoints", [])
            if isinstance(endpoints, list):
                for endpoint in endpoints:
                    if isinstance(endpoint, dict):
                        path = endpoint.get("path", "").lower()
                        parts = [p for p in path.split("/") if p and p not in ["api", "v1", "v2"]]
                        if parts:
                            entity = parts[0]
                            if entity not in db.lower() and entity.rstrip('s') not in db.lower():
                                issues.append(f"API endpoint '{path}' seems to reference a missing DB entity: {entity}")

        if not issues:
            print("[Agent] Validation successful! No issues found.")
            return schemas, 0

        print(f"[Agent] Found {len(issues)} issues. Initiating self-correction...")
        for issue in issues:
            print(f"  - {issue}")

        repair_prompt = f"""
        You are a Self-Correction Agent. The following schemas have consistency issues:
        {json.dumps(issues, indent=2)}
        
        Current Schemas:
        UI: {json.dumps(ui)}
        API: {json.dumps(api)}
        DB: {db}
        
        Please repair the schemas to ensure 100% consistency. 
        Return the corrected versions in the same JSON format:
        {{
          "ui_layout": <Object>,
          "api_endpoints": <Object>,
          "db_schema": <String>
        }}
        """
        
        response = self.model.generate_content(
            repair_prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        corrected_schemas = json.loads(response.text)
        print("[Agent] Repair completed.")
        return corrected_schemas, 1
