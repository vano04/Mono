from __future__ import annotations

import os

from runtrace import RunTrace


expected = os.environ["RUNTRACE_RUN_ID"]
client = RunTrace(
    base_url=os.environ["RUNTRACE_BASE_URL"],
    api_token=os.environ["RUNTRACE_API_TOKEN"],
    strict=True,
)

with client.run("qa-project", "SDK-attached child", "SDK attaches to the MCP-created run") as tracked:
    if tracked.id != expected:
        raise RuntimeError(f"attached id mismatch: {tracked.id} != {expected}")
    print(f"sdk-attached-run-id={tracked.id}", flush=True)
    tracked.log_metric("attached_score", 7.0, step=2)
    tracked.log_event("SDK attached without creating a duplicate", event_type="qa")
    tracked.finish("success", "Attached child completed", "One MCP-created run was reused")
