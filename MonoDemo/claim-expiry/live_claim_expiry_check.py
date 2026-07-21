from __future__ import annotations

import time
from uuid import uuid4

import httpx

from mono.credentials import resolve_connection


PROJECT = "integration-test-registry"


def main() -> None:
    base_url, token = resolve_connection()
    if base_url != "http://localhost:8000" or not token:
        raise RuntimeError("The isolated local Mono credential is required")
    worker_id = f"codex-claim-expiry-{uuid4().hex[:10]}"
    experiment_id: str | None = None
    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(base_url=base_url, headers=headers, timeout=30) as client:
        try:
            response = client.post(
                f"/api/v1/projects/{PROJECT}/experiments",
                json={
                    "title": "Disposable abandoned-claim expiry QA",
                    "hypothesis": "A stale pending claim returns to the shared queue.",
                    "reasoning": "Synthetic isolated-stack timing verification.",
                    "source": "agent",
                    "source_model": "codex",
                },
            )
            response.raise_for_status()
            experiment_id = response.json()["id"]

            response = client.post(
                f"/api/v1/projects/{PROJECT}/experiments/{experiment_id}/claim",
                json={"worker_id": worker_id, "request_id": f"{worker_id}-claim"},
            )
            response.raise_for_status()
            assert response.json()["lifecycle"] == "pending"

            time.sleep(2.1)
            response = client.get(f"/api/v1/projects/{PROJECT}/context")
            response.raise_for_status()
            response = client.get(
                f"/api/v1/projects/{PROJECT}/experiments/{experiment_id}"
            )
            response.raise_for_status()
            experiment = response.json()
            assert experiment["lifecycle"] == "proposed", experiment
            assert experiment["claimed_by"] is None, experiment
            print("live claim-expiry verification: abandoned claim requeued after timeout")
        finally:
            if experiment_id:
                current = client.get(
                    f"/api/v1/projects/{PROJECT}/experiments/{experiment_id}"
                )
                if current.status_code == 200 and current.json()["lifecycle"] == "pending":
                    client.post(
                        f"/api/v1/projects/{PROJECT}/experiments/{experiment_id}/release",
                        json={"worker_id": worker_id},
                    ).raise_for_status()
                response = client.delete(
                    f"/api/v1/projects/{PROJECT}/experiments/{experiment_id}"
                )
                if response.status_code not in {204, 404}:
                    response.raise_for_status()


if __name__ == "__main__":
    main()
