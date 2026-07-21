from __future__ import annotations

import os

from runtrace import RunTrace


client = RunTrace(
    base_url=os.environ["RUNTRACE_BASE_URL"],
    api_token=os.environ["RUNTRACE_API_TOKEN"],
    strict=True,
)

with client.run("qa-project", "SDK-crashing child", "SDK crash closure is reported") as tracked:
    print(f"sdk-crash-run-id={tracked.id}", flush=True)
    raise RuntimeError("intentional synthetic child crash")
