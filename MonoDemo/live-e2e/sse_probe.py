from __future__ import annotations

import json

import httpx

from mono.credentials import resolve_connection


PROJECT = "integration-test-registry"


def first_frame(base_url: str, token: str, run_id: str) -> dict[str, object]:
    headers = {"Authorization": f"Bearer {token}"}
    timeout = httpx.Timeout(5, read=5)
    with httpx.Client(base_url=base_url, headers=headers, timeout=timeout) as client:
        with client.stream("GET", f"/api/v1/runs/{run_id}/stream") as response:
            result: dict[str, object] = {
                "status": response.status_code,
                "content_type": response.headers.get("content-type"),
                "cache_control": response.headers.get("cache-control"),
                "transfer_encoding": response.headers.get("transfer-encoding"),
                "content_encoding": response.headers.get("content-encoding"),
            }
            try:
                for line in response.iter_lines():
                    if line.startswith("event: "):
                        result["first_event"] = line
                        return result
            except httpx.ReadTimeout:
                result["first_event"] = "read_timeout"
                return result
    raise AssertionError(f"{base_url} returned no SSE event")


def main() -> None:
    api_url, token = resolve_connection()
    assert api_url == "http://localhost:8000"
    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(base_url=api_url, headers=headers, timeout=15) as client:
        response = client.post(
            f"/api/v1/projects/{PROJECT}/runs",
            json={"name": "SSE isolation probe", "hypothesis": "Direct and proxied streams should flush immediately."},
        )
        response.raise_for_status()
        run_id = response.json()["id"]
        try:
            metric = client.post(
                f"/api/v1/runs/{run_id}/metrics",
                json={"metrics": [{"name": "qa_score", "value": 1, "step": 1}]},
            )
            metric.raise_for_status()
            results: dict[str, object] = {}
            for label, base_url in (("direct", api_url), ("web_proxy", "http://localhost:3000")):
                results[label] = first_frame(base_url, token, run_id)
            print(json.dumps(results, indent=2))
        finally:
            client.post(f"/api/v1/runs/{run_id}/crash", json={"error_summary": "Expected terminal cleanup after SSE probe"}).raise_for_status()


if __name__ == "__main__":
    main()
