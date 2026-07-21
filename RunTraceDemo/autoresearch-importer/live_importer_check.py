from __future__ import annotations

import argparse
import asyncio
import importlib.util
import os
from pathlib import Path

import httpx


ROOT = Path(__file__).resolve().parents[2]
TSV = Path(__file__).with_name("results.tsv")
PROJECT = "integration-test-autoresearch-importer"
BASE_URL = "http://localhost:8000"
TEST_USERNAME = os.getenv("RUNTRACE_TEST_USERNAME", "integration-owner")
TEST_PASSWORD = os.environ["RUNTRACE_TEST_PASSWORD"]


def load_importer():
    path = ROOT / "scripts" / "sync_autoresearch_results.py"
    spec = importlib.util.spec_from_file_location("sync_autoresearch_results_live", path)
    if not spec or not spec.loader:
        raise RuntimeError(f"Could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def main() -> None:
    importer = load_importer()
    token_id: str | None = None
    project_created = False
    with httpx.Client(base_url=BASE_URL, timeout=30) as owner:
        login = owner.post(
            "/api/v1/auth/login",
            json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
        )
        login.raise_for_status()
        try:
            created = owner.post(
                "/api/v1/projects",
                json={
                    "name": "Integration Test Autoresearch Importer",
                    "slug": PROJECT,
                    "description": "Disposable live verification of every importer transport.",
                },
            )
            created.raise_for_status()
            project = created.json()
            project_created = True

            token_response = owner.post(
                "/api/v1/auth/tokens",
                json={
                    "name": "Disposable importer verification",
                    "expires_in_days": 1,
                    "project_ids": [project["id"]],
                },
            )
            token_response.raise_for_status()
            token_payload = token_response.json()
            token_id = token_payload["api_token"]["id"]
            os.environ["RUNTRACE_API_TOKEN"] = token_payload["token"]
            os.environ["RUNTRACE_BASE_URL"] = BASE_URL

            args = argparse.Namespace(
                tsv=TSV,
                project=PROJECT,
                base_url=BASE_URL,
                transports=set(importer.TRANSPORTS),
            )
            await importer.run(args)
            await importer.run(args)

            bearer = httpx.Client(
                base_url=BASE_URL,
                headers={"Authorization": f"Bearer {token_payload['token']}"},
                timeout=30,
            )
            try:
                runs_response = bearer.get(
                    f"/api/v1/projects/{PROJECT}/runs?include_archived=true"
                )
                runs_response.raise_for_status()
                runs = [
                    run
                    for run in runs_response.json()
                    if run.get("configuration", {}).get("source_file") == "results.tsv"
                ]
            finally:
                bearer.close()

            assert len(runs) == 4, runs
            by_row = {run["configuration"]["source_row"]: run for run in runs}
            assert set(by_row) == {1, 2, 3, 4}
            assert [by_row[index]["configuration"]["sync_transport"] for index in (1, 2, 3, 4)] == [
                "http",
                "python",
                "mcp",
                "http",
            ]
            assert [by_row[index]["lifecycle"] for index in (1, 2, 3, 4)] == [
                "completed",
                "completed",
                "completed",
                "crashed",
            ]
            assert [by_row[index]["disposition"] for index in (1, 2, 3)] == [
                "kept",
                "discarded",
                "kept",
            ]
            print("live importer verification: 4 transports/status rows verified; replay skipped all 4")
        finally:
            os.environ.pop("RUNTRACE_API_TOKEN", None)
            os.environ.pop("RUNTRACE_BASE_URL", None)
            if token_id:
                response = owner.delete(f"/api/v1/auth/tokens/{token_id}")
                response.raise_for_status()
            if project_created:
                response = owner.delete(f"/api/v1/projects/{PROJECT}")
                response.raise_for_status()


if __name__ == "__main__":
    asyncio.run(main())
