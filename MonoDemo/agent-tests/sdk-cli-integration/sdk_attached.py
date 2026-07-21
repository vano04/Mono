from __future__ import annotations

import os

from mono import Mono


expected = os.environ["MONO_RUN_ID"]
client = Mono(
    base_url=os.environ["MONO_BASE_URL"],
    api_token=os.environ["MONO_API_TOKEN"],
    strict=True,
)

with client.run("qa-project", "SDK-attached child", "SDK attaches to the MCP-created run") as tracked:
    if tracked.id != expected:
        raise RuntimeError(f"attached id mismatch: {tracked.id} != {expected}")
    print(f"sdk-attached-run-id={tracked.id}", flush=True)
    tracked.log_metric("attached_score", 7.0, step=2)
    tracked.log_event("SDK attached without creating a duplicate", event_type="qa")
    tracked.finish("success", "Attached child completed", "One MCP-created run was reused")
