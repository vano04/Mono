from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import httpx

from mono.credentials import resolve_connection


PROJECT = "integration-test-registry"


class RuntimeValidation:
    def __init__(self) -> None:
        base_url, token = resolve_connection()
        if base_url != "http://localhost:8000":
            raise RuntimeError(f"Expected the isolated local stack, got {base_url!r}")
        if not token:
            raise RuntimeError("No saved Mono credential is available")

        self.marker = (
            "pg-runtime-"
            + datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
            + "-"
            + uuid4().hex[:8]
        )
        self.client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
            limits=httpx.Limits(max_connections=64, max_keepalive_connections=32),
        )
        self.run_ids: set[str] = set()
        self.experiment_ids: set[str] = set()
        self.visualization_ids: set[str] = set()
        self.original_baseline_run_id: str | None = None
        self.results: list[dict[str, Any]] = []

    async def raw(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> httpx.Response:
        headers = {"X-Request-ID": request_id} if request_id else None
        return await self.client.request(method, path, json=body, headers=headers)

    async def expect(
        self,
        method: str,
        path: str,
        status: int,
        *,
        body: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> httpx.Response:
        response = await self.raw(
            method,
            path,
            body=body,
            request_id=request_id,
        )
        if response.status_code != status:
            detail = response.text[:800].replace("\n", " ")
            raise AssertionError(
                f"{method} {path}: expected HTTP {status}, "
                f"got {response.status_code}: {detail}"
            )
        return response

    async def create_run(
        self,
        suffix: str,
        *,
        experiment_id: str | None = None,
        worker_id: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "name": f"{self.marker}-{suffix}",
            "hypothesis": "PostgreSQL runtime invariants remain correct under concurrency.",
            "reasoning": "Synthetic permission-enabled QA; no repository behavior is changed.",
            "change_summary": "Runtime-only PostgreSQL validation.",
            "configuration": {"synthetic": True, "qa_marker": self.marker},
        }
        if experiment_id:
            body["experiment_id"] = experiment_id
        if worker_id:
            body["worker_id"] = worker_id
        response = await self.expect(
            "POST",
            f"/api/v1/projects/{PROJECT}/runs",
            201,
            body=body,
        )
        payload = response.json()
        self.run_ids.add(payload["id"])
        return payload

    async def finish_run(
        self,
        run_id: str,
        suffix: str,
        *,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        response = await self.expect(
            "POST",
            f"/api/v1/runs/{run_id}/finish",
            200,
            body={
                "disposition": "undecided",
                "result_summary": f"{self.marker}-{suffix}",
                "conclusion": "Synthetic PostgreSQL validation completed.",
            },
            request_id=request_id,
        )
        return response.json()

    async def create_experiment(self, suffix: str) -> dict[str, Any]:
        response = await self.expect(
            "POST",
            f"/api/v1/projects/{PROJECT}/experiments",
            201,
            body={
                "title": f"{self.marker}-{suffix}",
                "hypothesis": "A PostgreSQL concurrency invariant is preserved.",
                "reasoning": "Synthetic runtime validation.",
                "source": "agent",
                "source_model": "codex",
                "configuration": {"synthetic": True, "qa_marker": self.marker},
            },
        )
        payload = response.json()
        self.experiment_ids.add(payload["id"])
        return payload

    async def verify_connection(self) -> None:
        auth = await self.expect("GET", "/api/v1/auth/status", 200)
        auth_payload = auth.json()
        if not auth_payload.get("authenticated"):
            raise AssertionError("Saved credential was not authenticated")
        project = await self.expect("GET", f"/api/v1/projects/{PROJECT}", 200)
        project_payload = project.json()
        self.original_baseline_run_id = project_payload["current_baseline_run_id"]
        self.results.append(
            {
                "case": "authenticated_connection",
                "project": project_payload["slug"],
                "identity_role": auth_payload["identity"]["role"],
                "original_baseline_run_id": self.original_baseline_run_id,
            }
        )

    async def verify_concurrent_display_ids(self) -> None:
        experiment_responses = await asyncio.gather(
            *(self.create_experiment(f"display-exp-{index}") for index in range(12))
        )
        experiment_display_ids = [item["display_id"] for item in experiment_responses]
        if len(set(experiment_display_ids)) != len(experiment_display_ids):
            raise AssertionError(f"Duplicate experiment display IDs: {experiment_display_ids}")

        run_responses = await asyncio.gather(
            *(self.create_run(f"display-run-{index}") for index in range(12))
        )
        run_display_ids = [item["display_id"] for item in run_responses]
        if len(set(run_display_ids)) != len(run_display_ids):
            raise AssertionError(f"Duplicate run display IDs: {run_display_ids}")

        finished = await asyncio.gather(
            *(
                self.finish_run(
                    item["id"],
                    f"display-run-{index}-done",
                    request_id=f"{self.marker}-display-finish-{index}",
                )
                for index, item in enumerate(run_responses)
            )
        )
        if any(item["lifecycle"] != "completed" for item in finished):
            raise AssertionError("A concurrent display-ID run did not become terminal")

        self.results.append(
            {
                "case": "concurrent_display_ids",
                "concurrent_experiments": len(experiment_display_ids),
                "concurrent_runs": len(run_display_ids),
                "unique_experiment_ids": len(set(experiment_display_ids)),
                "unique_run_ids": len(set(run_display_ids)),
                "experiment_range": sorted(experiment_display_ids),
                "run_range": sorted(run_display_ids),
            }
        )

    async def verify_claim_and_start(self) -> None:
        experiment = await self.create_experiment("claim-start")
        claim_path = f"/api/v1/projects/{PROJECT}/experiments/{experiment['id']}/claim"
        workers = [f"{self.marker}-worker-a", f"{self.marker}-worker-b"]
        claim_responses = await asyncio.gather(
            *(
                self.raw(
                    "POST",
                    claim_path,
                    body={"worker_id": worker, "request_id": f"{worker}-claim"},
                )
                for worker in workers
            )
        )
        claim_statuses = sorted(response.status_code for response in claim_responses)
        if claim_statuses != [200, 409]:
            raise AssertionError(f"Expected one claim winner and one conflict, got {claim_statuses}")
        winner_payload = next(response.json() for response in claim_responses if response.status_code == 200)
        winner = winner_payload["claimed_by"]

        start_body = {
            "experiment_id": experiment["id"],
            "worker_id": winner,
            "name": f"{self.marker}-claimed-run",
            "hypothesis": "Only the claim owner can start one run.",
            "reasoning": "Concurrent start against one pending experiment.",
            "configuration": {"synthetic": True, "qa_marker": self.marker},
        }
        start_responses = await asyncio.gather(
            *(
                self.raw(
                    "POST",
                    f"/api/v1/projects/{PROJECT}/runs",
                    body=start_body,
                )
                for _ in range(2)
            )
        )
        start_statuses = sorted(response.status_code for response in start_responses)
        if start_statuses != [201, 409]:
            raise AssertionError(f"Expected one start winner and one conflict, got {start_statuses}")
        started = next(response.json() for response in start_responses if response.status_code == 201)
        self.run_ids.add(started["id"])
        finished = await self.finish_run(
            started["id"],
            "claimed-run-done",
            request_id=f"{self.marker}-claimed-finish",
        )
        if finished["lifecycle"] != "completed":
            raise AssertionError("Claimed run did not complete")

        self.results.append(
            {
                "case": "claim_and_start",
                "claim_statuses": claim_statuses,
                "start_statuses": start_statuses,
                "winner": winner,
                "run_display_id": started["display_id"],
            }
        )

    async def verify_terminal_replay(self) -> None:
        finish_run = await self.create_run("finish-replay")
        cross_run = await self.create_run("finish-replay-cross-run")
        finish_request_id = f"{self.marker}-finish-replay"
        finish_responses = await asyncio.gather(
            self.raw(
                "POST",
                f"/api/v1/runs/{finish_run['id']}/finish",
                body={
                    "disposition": "kept",
                    "result_summary": f"{self.marker}-finish-a",
                    "conclusion": "first concurrent terminal candidate",
                },
                request_id=finish_request_id,
            ),
            self.raw(
                "POST",
                f"/api/v1/runs/{finish_run['id']}/finish",
                body={
                    "disposition": "discarded",
                    "result_summary": f"{self.marker}-finish-b",
                    "conclusion": "second concurrent terminal candidate",
                },
                request_id=finish_request_id,
            ),
        )
        if [response.status_code for response in finish_responses] != [200, 200]:
            raise AssertionError(
                "Concurrent finish replay statuses were "
                f"{[response.status_code for response in finish_responses]}"
            )
        finish_payloads = [response.json() for response in finish_responses]
        summaries = {item["result_summary"] for item in finish_payloads}
        if len(summaries) != 1:
            raise AssertionError(f"Idempotent finish responses diverged: {summaries}")
        winning_summary = summaries.pop()
        late_replay = await self.expect(
            "POST",
            f"/api/v1/runs/{finish_run['id']}/finish",
            200,
            body={
                "disposition": "undecided",
                "result_summary": f"{self.marker}-late-mutation",
                "conclusion": "must not overwrite the terminal record",
            },
            request_id=finish_request_id,
        )
        if late_replay.json()["result_summary"] != winning_summary:
            raise AssertionError("Late finish replay mutated the terminal result")

        cross_response = await self.expect(
            "POST",
            f"/api/v1/runs/{cross_run['id']}/finish",
            200,
            body={
                "disposition": "undecided",
                "result_summary": f"{self.marker}-cross-run-independent",
                "conclusion": "The same request ID is scoped per run.",
            },
            request_id=finish_request_id,
        )
        if cross_response.json()["result_summary"] != f"{self.marker}-cross-run-independent":
            raise AssertionError("Finish replay leaked across runs")

        crash_run = await self.create_run("crash-replay")
        crash_request_id = f"{self.marker}-crash-replay"
        crash_responses = await asyncio.gather(
            self.raw(
                "POST",
                f"/api/v1/runs/{crash_run['id']}/crash",
                body={"error_summary": f"{self.marker}-crash-a"},
                request_id=crash_request_id,
            ),
            self.raw(
                "POST",
                f"/api/v1/runs/{crash_run['id']}/crash",
                body={"error_summary": f"{self.marker}-crash-b"},
                request_id=crash_request_id,
            ),
        )
        if [response.status_code for response in crash_responses] != [200, 200]:
            raise AssertionError(
                "Concurrent crash replay statuses were "
                f"{[response.status_code for response in crash_responses]}"
            )
        crash_summaries = {response.json()["result_summary"] for response in crash_responses}
        if len(crash_summaries) != 1:
            raise AssertionError(f"Idempotent crash responses diverged: {crash_summaries}")
        crash_summary = crash_summaries.pop()
        late_crash = await self.expect(
            "POST",
            f"/api/v1/runs/{crash_run['id']}/crash",
            200,
            body={"error_summary": f"{self.marker}-late-crash-mutation"},
            request_id=crash_request_id,
        )
        if late_crash.json()["result_summary"] != crash_summary:
            raise AssertionError("Late crash replay mutated the terminal result")

        self.results.append(
            {
                "case": "terminal_replay",
                "finish_request_id": finish_request_id,
                "finish_run_ids": [finish_run["id"], cross_run["id"]],
                "finish_statuses": [response.status_code for response in finish_responses],
                "finish_winning_summary": winning_summary,
                "crash_request_id": crash_request_id,
                "crash_run_id": crash_run["id"],
                "crash_statuses": [response.status_code for response in crash_responses],
                "crash_winning_summary": crash_summary,
            }
        )

    async def verify_baseline_delete(self) -> None:
        run = await self.create_run("baseline-delete")
        await self.finish_run(
            run["id"],
            "baseline-delete-complete",
            request_id=f"{self.marker}-baseline-finish",
        )
        await self.expect(
            "POST",
            f"/api/v1/projects/{PROJECT}/baseline",
            200,
            body={
                "run_id": run["id"],
                "actor": "codex-postgres-runtime-qa",
                "request_id": f"{self.marker}-set-baseline",
            },
        )
        before = (await self.expect("GET", f"/api/v1/projects/{PROJECT}", 200)).json()
        if before["current_baseline_run_id"] != run["id"]:
            raise AssertionError("Completed run was not installed as the baseline")
        await self.expect("DELETE", f"/api/v1/runs/{run['id']}", 204)
        after = (await self.expect("GET", f"/api/v1/projects/{PROJECT}", 200)).json()
        if after["current_baseline_run_id"] is not None:
            raise AssertionError("Deleting the baseline left a stale project reference")
        deleted = await self.raw("GET", f"/api/v1/runs/{run['id']}")
        if deleted.status_code != 404:
            raise AssertionError(f"Deleted baseline run remained visible: HTTP {deleted.status_code}")

        self.results.append(
            {
                "case": "baseline_delete",
                "baseline_before_delete": run["id"],
                "baseline_after_delete": after["current_baseline_run_id"],
                "deleted_run_status": deleted.status_code,
            }
        )

    async def verify_visualization_source_delete(self) -> None:
        run = await self.create_run("visualization-source")
        await self.expect(
            "POST",
            f"/api/v1/runs/{run['id']}/metrics",
            202,
            body={
                "metrics": [
                    {
                        "name": "postgres_runtime_score",
                        "value": 42.25,
                        "step": 1,
                        "context": {"synthetic": True},
                    }
                ]
            },
            request_id=f"{self.marker}-visualization-metric",
        )
        await self.finish_run(
            run["id"],
            "visualization-source-complete",
            request_id=f"{self.marker}-visualization-finish",
        )
        spec = {
            "$schema": "https://mono.dev/schemas/rtvis/v1.json",
            "version": 1,
            "title": f"{self.marker} source-run metrics",
            "description": "Synthetic source-run reference validation.",
            "datasets": {
                "metrics": {"source": "mono", "query": "run_metrics"}
            },
            "view": {
                "type": "chart",
                "dataset": "metrics",
                "chart": "line",
                "x": "step",
                "y": "value",
                "series": "name",
            },
        }
        created = await self.expect(
            "POST",
            f"/api/v1/projects/{PROJECT}/visualizations",
            201,
            body={
                "name": f"{self.marker}-source-visualization",
                "description": "Synthetic PostgreSQL reference-integrity QA.",
                "spec": spec,
                "source_run_id": run["id"],
                "created_by": "codex-postgres-runtime-qa",
            },
        )
        visualization = created.json()
        self.visualization_ids.add(visualization["id"])
        rows = visualization["resolved_datasets"]["metrics"]
        if not any(
            row.get("name") == "postgres_runtime_score" and row.get("value") == 42.25
            for row in rows
        ):
            raise AssertionError(f"Source-run metric was not resolved: {rows}")

        protected = await self.raw("DELETE", f"/api/v1/runs/{run['id']}")
        if protected.status_code != 409:
            raise AssertionError(
                "Visualization source deletion should be blocked, got "
                f"HTTP {protected.status_code}"
            )
        await self.expect(
            "DELETE",
            f"/api/v1/projects/{PROJECT}/visualizations/{visualization['id']}",
            204,
        )
        self.visualization_ids.discard(visualization["id"])
        await self.expect("DELETE", f"/api/v1/runs/{run['id']}", 204)
        deleted = await self.raw("GET", f"/api/v1/runs/{run['id']}")
        if deleted.status_code != 404:
            raise AssertionError(f"Unreferenced source run remained visible: HTTP {deleted.status_code}")

        self.results.append(
            {
                "case": "visualization_source_delete",
                "resolved_metric_rows": len(rows),
                "delete_while_referenced": protected.status_code,
                "delete_after_visualization": 204,
                "deleted_run_status": deleted.status_code,
            }
        )

    async def cleanup(self) -> dict[str, Any]:
        failures: list[str] = []
        crashed = 0
        deleted_runs = 0
        deleted_experiments = 0
        deleted_visualizations = 0
        baseline_restored = False

        for visualization_id in list(self.visualization_ids):
            response = await self.raw(
                "DELETE",
                f"/api/v1/projects/{PROJECT}/visualizations/{visualization_id}",
            )
            if response.status_code in {204, 404}:
                if response.status_code == 204:
                    deleted_visualizations += 1
            else:
                failures.append(
                    f"visualization {visualization_id}: HTTP {response.status_code}"
                )

        for run_id in list(self.run_ids):
            current = await self.raw("GET", f"/api/v1/runs/{run_id}")
            if current.status_code == 404:
                continue
            if current.status_code != 200:
                failures.append(f"read run {run_id}: HTTP {current.status_code}")
                continue
            if current.json().get("lifecycle") == "running":
                crashed_response = await self.raw(
                    "POST",
                    f"/api/v1/runs/{run_id}/crash",
                    body={"error_summary": "Synthetic PostgreSQL QA cleanup"},
                    request_id=f"{self.marker}-cleanup-{run_id}",
                )
                if crashed_response.status_code == 200:
                    crashed += 1
                else:
                    failures.append(
                        f"crash run {run_id}: HTTP {crashed_response.status_code}"
                    )
                    continue
            deleted_response = await self.raw("DELETE", f"/api/v1/runs/{run_id}")
            if deleted_response.status_code in {204, 404}:
                if deleted_response.status_code == 204:
                    deleted_runs += 1
            else:
                failures.append(
                    f"delete run {run_id}: HTTP {deleted_response.status_code}"
                )

        for experiment_id in list(self.experiment_ids):
            response = await self.raw(
                "DELETE",
                f"/api/v1/projects/{PROJECT}/experiments/{experiment_id}",
            )
            if response.status_code in {204, 404}:
                if response.status_code == 204:
                    deleted_experiments += 1
            else:
                failures.append(
                    f"delete experiment {experiment_id}: HTTP {response.status_code}"
                )

        if self.original_baseline_run_id:
            response = await self.raw(
                "POST",
                f"/api/v1/projects/{PROJECT}/baseline",
                body={
                    "run_id": self.original_baseline_run_id,
                    "actor": "codex-postgres-runtime-qa-cleanup",
                    "request_id": f"{self.marker}-restore-original-baseline",
                },
            )
            if response.status_code == 200:
                baseline_restored = True
            else:
                failures.append(
                    "restore original baseline "
                    f"{self.original_baseline_run_id}: HTTP {response.status_code}"
                )

        return {
            "crashed_running_runs": crashed,
            "deleted_runs": deleted_runs,
            "deleted_experiments": deleted_experiments,
            "deleted_visualizations": deleted_visualizations,
            "original_baseline_restored": baseline_restored,
            "failures": failures,
        }

    async def run(self) -> None:
        error: BaseException | None = None
        try:
            await self.verify_connection()
            await self.verify_concurrent_display_ids()
            await self.verify_claim_and_start()
            await self.verify_terminal_replay()
            await self.verify_baseline_delete()
            await self.verify_visualization_source_delete()
        except BaseException as exc:
            error = exc
        finally:
            cleanup = await self.cleanup()
            await self.client.aclose()

        report = {
            "marker": self.marker,
            "project": PROJECT,
            "results": self.results,
            "cleanup": cleanup,
        }
        print(json.dumps(report, indent=2, sort_keys=True))
        if cleanup["failures"]:
            raise RuntimeError(f"Cleanup failures: {cleanup['failures']}")
        if error:
            raise error


if __name__ == "__main__":
    asyncio.run(RuntimeValidation().run())
