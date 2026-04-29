import json
import os
import time
from agents import SaaSCompiler

def run_test_suite():
    prompts = [
        "Offline-first task manager with P2P sync and local-first DB",
        "Crypto portfolio tracker with real-time price alerts and multi-exchange integration",
        "Healthcare portal with HIPAA compliance, audit logs, and patient-doctor messaging",
        "Subscription-only video streaming service with tiered access (Free, Pro, Enterprise)",
        "Multi-tenant inventory for luxury car rentals with geolocation and booking engine",
        "AI-powered legal document analyzer with OCR and automated risk assessment",
        "Real-time collaborative whiteboard with infinite canvas and version history",
        "Decentralized social network with IPFS storage and cryptographic identity",
        "IoT fleet management dashboard with real-time telemetry and predictive maintenance",
        "Global e-commerce with multi-currency, localization, and complex tax rules"
    ]

    compiler = SaaSCompiler()
    results = []
    total_repairs = 0
    success_count = 0

    print(f"Starting test suite with {len(prompts)} edge cases...\n")
    print("Note: Exponential backoff is enabled for rate-limit handling.\n")

    for i, prompt in enumerate(prompts):
        print(f"[{i+1}/{len(prompts)}] Testing: {prompt}")
        start_time = time.time()
        try:
            # 1. Design
            design = compiler.generate_design(prompt)
            
            # 2. Schemas
            schemas = compiler.generate_schemas(design)
            
            # 3. Validate & Repair
            final_schemas, repair_count = compiler.validate_and_repair(schemas)
            
            duration = time.time() - start_time
            results.append({
                "prompt": prompt,
                "status": "SUCCESS",
                "duration": round(duration, 2),
                "repairs": repair_count
            })
            total_repairs += repair_count
            success_count += 1
            print(f"  Result: SUCCESS (Repairs: {repair_count}, Time: {round(duration, 2)}s)\n")
        except Exception as e:
            print(f"  Result: FAILED ({str(e)})\n")
            results.append({
                "prompt": prompt,
                "status": "FAILED",
                "error": str(e)
            })

    metrics = {
        "timestamp": time.ctime(),
        "total_cases": len(prompts),
        "success_rate": f"{(success_count / len(prompts)) * 100}%",
        "total_repairs": total_repairs,
        "average_repairs": total_repairs / len(prompts) if len(prompts) > 0 else 0,
        "detailed_results": results
    }

    with open("metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

    print(f"Test suite completed. Results saved to metrics.json")
    print(f"Success Rate: {metrics['success_rate']}")
    print(f"Total Repairs: {metrics['total_repairs']}")

if __name__ == "__main__":
    run_test_suite()
