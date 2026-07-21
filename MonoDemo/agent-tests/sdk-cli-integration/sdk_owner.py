from __future__ import annotations

import os

from mono import Mono


client = Mono(
    base_url=os.environ["MONO_BASE_URL"],
    api_token=os.environ["MONO_API_TOKEN"],
    strict=True,
)

with client.run("qa-project", "SDK-owned run", "SDK owns exactly one lifecycle") as tracked:
    print(f"sdk-run-id={tracked.id}", flush=True)
    tracked.log_metric("sdk_score", 4.5, step=1)
    tracked.log_event("SDK owner recorded evidence", level="info", event_type="qa")
    tracked.finish("success", "SDK child completed", "SDK owned the run")
