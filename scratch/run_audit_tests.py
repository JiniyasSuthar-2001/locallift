import os
import sys
import subprocess
import glob
import json

test_files = sorted(glob.glob("backend/test_*.py"))
results = {}

for tf in test_files:
    cmd = [sys.executable, "-m", "pytest", tf, "-q", "--disable-warnings"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        output = proc.stdout + "\n" + proc.stderr
        status = "PASSED" if proc.returncode == 0 else "FAILED"
        results[tf] = {
            "status": status,
            "returncode": proc.returncode,
            "output": output.strip()[-500:]  # last 500 chars
        }
        print(f"{tf}: {status} (code {proc.returncode})")
    except subprocess.TimeoutExpired:
        results[tf] = {"status": "TIMEOUT", "returncode": -1, "output": "Execution timed out (60s)"}
        print(f"{tf}: TIMEOUT")
    except Exception as e:
        results[tf] = {"status": "ERROR", "returncode": -2, "output": str(e)}
        print(f"{tf}: ERROR ({str(e)})")

with open("scratch/test_summary.json", "w") as f:
    json.dump(results, f, indent=2)

print("\nAudit test run complete. Summary saved to scratch/test_summary.json")
