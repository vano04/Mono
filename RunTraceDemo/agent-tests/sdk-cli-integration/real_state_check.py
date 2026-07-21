from __future__ import annotations

from runtrace import RunTrace
from runtrace.credentials import resolve_connection


PROJECT = "permission-qa-registry"
PREFIX = "codex-qa-sdk-cli-20260721"
base_url, token = resolve_connection()
client = RunTrace(base_url=base_url, api_token=token, strict=True)
runs = client.request("GET", f"/api/v1/projects/{PROJECT}/runs")
owned = [item for item in runs if item["name"].startswith(PREFIX)]
nonterminal = [item for item in owned if item["lifecycle"] not in {"completed", "crashed"}]
if nonterminal:
    raise RuntimeError("non-terminal QA run: " + ",".join(item["id"] for item in nonterminal))
print(f"qa-run-count={len(owned)}")
print(f"qa-nonterminal-count={len(nonterminal)}")
for item in sorted(owned, key=lambda value: value["name"]):
    print(f"qa-run={item['id']}|{item['name']}|{item['lifecycle']}|{item.get('disposition')}")
