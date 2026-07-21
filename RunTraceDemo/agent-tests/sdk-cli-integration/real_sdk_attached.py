from __future__ import annotations

import os

from runtrace import RunTrace
from runtrace.credentials import resolve_connection


PROJECT = "permission-qa-registry"
expected_id = os.environ["RUNTRACE_RUN_ID"]
base_url, token = resolve_connection()
client = RunTrace(base_url=base_url, api_token=token, strict=True)

with client.run(
    PROJECT,
    "codex-qa-sdk-cli-20260721-sdk-attached",
    "The SDK attaches to the MCP-created running record without creating a second run.",
    "MCP is the creator; RUNTRACE_RUN_ID is the lifecycle handoff.",
    tags=["qa", "attachment", "synthetic"],
) as tracked:
    if tracked.id != expected_id:
        raise RuntimeError("SDK attached to an unexpected run id")
    tracked.log_metric("qa_score", 2.0, step=1)
    tracked.log_event("SDK attached to existing MCP-created run", event_type="qa")
    tracked.finish(
        "success",
        "Existing-run attachment completed",
        "The SDK reused the MCP-created run and did not create a duplicate.",
    )

detail = client.request("GET", f"/api/v1/runs/{expected_id}")
assert detail["lifecycle"] == "completed"
assert detail["metrics"]["qa_score"]["latest"] == 2.0
print(f"sdk-attached-run-id={expected_id}")
print(f"sdk-attached-lifecycle={detail['lifecycle']}")
