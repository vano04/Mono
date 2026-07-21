from __future__ import annotations

from mono import Mono
from mono.credentials import resolve_connection


PROJECT = "integration-test-registry"
PREFIX = "integration-sdk-cli"
base_url, token = resolve_connection()
client = Mono(base_url=base_url, api_token=token, strict=True)
runs = client.request("GET", f"/api/v1/projects/{PROJECT}/runs")
owned = [item for item in runs if item["name"].startswith(PREFIX)]
nonterminal = [item for item in owned if item["lifecycle"] not in {"completed", "crashed"}]
if nonterminal:
    raise RuntimeError("non-terminal QA run: " + ",".join(item["id"] for item in nonterminal))
print(f"qa-run-count={len(owned)}")
print(f"qa-nonterminal-count={len(nonterminal)}")
for item in sorted(owned, key=lambda value: value["name"]):
    print(f"qa-run={item['id']}|{item['name']}|{item['lifecycle']}|{item.get('disposition')}")
