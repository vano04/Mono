from __future__ import annotations

import time

import httpx


BASE_URL = "http://localhost:8100"


def run_step(client: httpx.Client) -> int:
    response = client.get("/api/v1/runs/run_174")
    response.raise_for_status()
    points = response.json()["metrics"]["validation_loss"]["points"]
    return max(point["step"] for point in points)


def claimed_at(client: httpx.Client) -> str:
    response = client.get(
        "/api/v1/projects/dense-optimizer/experiments/exp_022"
    )
    response.raise_for_status()
    experiment = response.json()
    assert experiment["lifecycle"] == "pending"
    assert experiment["claimed_by"] == "autoresearch/Jul4"
    return experiment["claimed_at"]


def main() -> None:
    with httpx.Client(base_url=BASE_URL, timeout=30) as client:
        response = client.get("/api/v1/auth/status")
        response.raise_for_status()
        status = response.json()
        assert status["dev"] is True
        assert status["authenticated"] is True
        assert status["identity"]["role"] == "owner"

        response = client.get("/api/v1/projects")
        response.raise_for_status()
        projects = response.json()
        assert {project["slug"] for project in projects} == {
            "dense-optimizer",
            "flash-attention-kernel",
            "sparse-router",
        }

        response = client.get("/api/v1/projects/dense-optimizer/dashboard")
        response.raise_for_status()
        dashboard = response.json()
        assert dashboard["baseline"]["id"] == "run_168"
        assert dashboard["worker_count"] == 6
        assert dashboard["access_role"] == "owner"

        first_step = run_step(client)
        first_claimed_at = claimed_at(client)
        time.sleep(11.2)
        second_step = run_step(client)
        second_claimed_at = claimed_at(client)
        expected_step = 0 if first_step >= 1000 else first_step + 100
        assert second_step == expected_step, (first_step, second_step)
        assert second_claimed_at > first_claimed_at, (
            first_claimed_at,
            second_claimed_at,
        )
        print(
            "live dev-seed verification: dev bypass, 3 seeded projects, baseline, "
            f"6 workers, metric loop {first_step}->{second_step}, claim keepalive advanced"
        )


if __name__ == "__main__":
    main()
