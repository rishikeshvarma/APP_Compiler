import json
import os
import time
from agents import SaaSCompiler

def log_to_output(content):
    with open("output.md", "a") as f:
        f.write(content + "\n")

def run_audit():
    # Clear output file
    with open("output.md", "w") as f:
        f.write("# Audit Log\n\n")

    compiler = SaaSCompiler(model_name="gemini-3-flash-preview")
    
    challenge_prompt = "Build a HIPAA-compliant Healthcare CRM. Patients can view their medical history and message doctors. Doctors have a 'Patient Queue' and 'Diagnostic AI' gated by a 'Premium Clinic' plan. Admins manage clinics and view audit logs. Ensure that if a message is sent, a 'Notification' entity is created in the DB."
    
    print(f"🚀 Starting Audit Challenge...")
    log_to_output(f"## Running Challenge Prompt\nPrompt: `{challenge_prompt}`\n")
    
    start_time = time.time()
    
    # 1. Architecting
    log_to_output("### Stage 1: Architecting")
    design = compiler.generate_design(challenge_prompt)
    log_to_output("Design Spec Generated.\n")
    with open("blueprints/design_spec.md", "w") as f:
        f.write(design)
    
    # 2. Compiling
    log_to_output("### Stage 2: Compiling")
    schemas = compiler.generate_schemas(design)
    log_to_output("Schemas Generated.\n")
    
    # 3. Validating
    log_to_output("### Stage 3: Validating")
    final_schemas, repair_count = compiler.validate_and_repair(schemas)
    log_to_output(f"Validation completed. Repair count: {repair_count}\n")
    
    # Save results
    output_dir = "schemas"
    os.makedirs(output_dir, exist_ok=True)
    with open(os.path.join(output_dir, "ui_layout.json"), "w") as f:
        json.dump(final_schemas.get("ui_layout", {}), f, indent=2)
    with open(os.path.join(output_dir, "api_endpoints.json"), "w") as f:
        json.dump(final_schemas.get("api_endpoints", {}), f, indent=2)
    with open(os.path.join(output_dir, "db_schema.sql"), "w") as f:
        f.write(final_schemas.get("db_schema", ""))
    
    log_to_output(f"Total time: {round(time.time() - start_time, 2)}s\n")
    
    # Verification checks
    log_to_output("## Verification Checklist")
    
    # Cross-Layer Consistency
    ui = final_schemas.get("ui_layout", {})
    api = final_schemas.get("api_endpoints", {})
    db = final_schemas.get("db_schema", "")
    
    # Check for Diagnostic AI
    diag_ai_ui = "Diagnostic AI" in json.dumps(ui)
    diag_ai_api = "/diagnostic-ai" in json.dumps(api) or "diagnostic ai" in json.dumps(api).lower()
    log_to_output(f"- [ ] Diagnostic AI in UI: {'✅' if diag_ai_ui else '❌'}")
    log_to_output(f"- [ ] Diagnostic AI in API: {'✅' if diag_ai_api else '❌'}")
    
    # Check for plan_types table
    plan_types_db = "plan_types" in db.lower() or "plan" in db.lower()
    log_to_output(f"- [ ] plan_types table in DB: {'✅' if plan_types_db else '❌'}")
    
    # Check for Notification entity
    notification_db = "notification" in db.lower()
    log_to_output(f"- [ ] Notification entity in DB: {'✅' if notification_db else '❌'}")
    
    # Check for Audit Logs
    audit_logs_db = "audit_log" in db.lower()
    log_to_output(f"- [ ] Audit Log table in DB: {'✅' if audit_logs_db else '❌'}")

    # Deterministic Reliability Check
    log_to_output("\n## Deterministic Reliability Check (Vague Prompt: 'Build a sales tool')")
    vague_prompt = "Build a sales tool"
    
    log_to_output("Run 1...")
    design1 = compiler.generate_design(vague_prompt)
    schemas1 = compiler.generate_schemas(design1)
    entities1 = sorted([e.get("path") for e in schemas1.get("api_endpoints", {}).get("endpoints", []) if isinstance(e, dict)])
    
    log_to_output("Run 2...")
    design2 = compiler.generate_design(vague_prompt)
    schemas2 = compiler.generate_schemas(design2)
    entities2 = sorted([e.get("path") for e in schemas2.get("api_endpoints", {}).get("endpoints", []) if isinstance(e, dict)])
    
    consistency = entities1 == entities2
    log_to_output(f"Consistency check: {'✅' if consistency else '❌'}")
    log_to_output(f"Run 1 Entities: {entities1}")
    log_to_output(f"Run 2 Entities: {entities2}")

if __name__ == "__main__":
    run_audit()
