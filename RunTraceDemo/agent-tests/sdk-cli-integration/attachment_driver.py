from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from runtrace import RunTrace


base_url = os.environ["RUNTRACE_BASE_URL"]
token = os.environ["RUNTRACE_API_TOKEN"]
client = RunTrace(base_url=base_url, api_token=token, strict=True)
created = client.request(
    "POST",
    "/api/v1/projects/qa-project/runs",
    {"name": "MCP-created attachment run", "hypothesis": "SDK reuses the running record"},
)

child_env = os.environ.copy()
child_env["RUNTRACE_RUN_ID"] = created["id"]
child = Path(__file__).with_name("sdk_attached.py")
result = subprocess.run(["uv", "run", "--no-project", "python", str(child)], env=child_env, text=True, capture_output=True)
sys.stdout.write(result.stdout)
sys.stderr.write(result.stderr)
if result.returncode:
    raise SystemExit(result.returncode)

snapshot = client.client.get("/__state").json()
matches = [run for run in snapshot["runs"] if run["id"] == created["id"]]
if len(matches) != 1:
    raise RuntimeError(f"duplicate attachment records: {len(matches)}")
print(f"attachment-run-id={created['id']}")
print(f"attachment-run-count={len(matches)}")
print(f"attachment-lifecycle={matches[0]['lifecycle']}")
