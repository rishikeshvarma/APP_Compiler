import requests
import json
import time

BASE_URL = "http://localhost:8000"

TEST_CASES = [
    {
        "name": "Vague",
        "prompt": "Build a social app."
    },
    {
        "name": "Conflicting",
        "prompt": "I want a CRM but without users or data storage."
    },
    {
        "name": "Complex",
        "prompt": "Build a multi-tenant ERP with role-based access, inventory tracking, and Stripe integration."
    }
]

def run_benchmarks():
    results = []
    print("Starting benchmarks...")
    
    for case in TEST_CASES:
        print(f"Running case: {case['name']}...")
        start_time = time.time()
        try:
            response = requests.post(f"{BASE_URL}/compile", json={"prompt": case["prompt"]}, timeout=60)
            data = response.json()
            latency = time.time() - start_time
            
            success = data.get("success", False)
            validation_status = data.get("validation", {}).get("status", "UNKNOWN")
            
            results.append({
                "case": case["name"],
                "success": success,
                "validation_status": validation_status,
                "latency_sec": round(latency, 2),
                "repair_triggered": any("Repairing" in log["step"] for log in data.get("logs", []))
            })
            print(f"Done: {case['name']} in {round(latency, 2)}s")
        except Exception as e:
            print(f"Error in {case['name']}: {str(e)}")
            results.append({
                "case": case["name"],
                "success": False,
                "error": str(e)
            })

    # Log to file
    with open("benchmark_results.log", "w") as f:
        f.write("=== AppCompiler Benchmark Results ===\n")
        f.write(f"Date: {time.ctime()}\n\n")
        for res in results:
            f.write(json.dumps(res, indent=2) + "\n---\n")
            
    success_rate = (len([r for r in results if r.get("success")]) / len(results)) * 100
    print(f"\nBenchmarks completed. Success Rate: {success_rate}%")
    print("Results saved to benchmark_results.log")

if __name__ == "__main__":
    # Ensure server is running or start it manually before running this
    try:
        run_benchmarks()
    except Exception as e:
        print(f"Failed to run benchmarks: {e}")
