from __future__ import annotations

import json
import threading
import time
from typing import Any, Callable

import httpx

from runtrace.credentials import resolve_connection


PROJECT = "permission-qa-registry"
WORKER = "api-matrix-worker"


def expect(response: httpx.Response, status: int, label: str) -> Any:
    if response.status_code != status:
        raise AssertionError(f"{label}: expected {status}, got {response.status_code}: {response.text[:500]}")
    if not response.content:
        return None
    content_type = response.headers.get("content-type", "")
    return response.json() if "json" in content_type else response.content


def sse_until(
    client: httpx.Client,
    path: str,
    done: Callable[[list[tuple[str, dict[str, Any]]]], bool],
) -> list[tuple[str, dict[str, Any]]]:
    frames: list[tuple[str, dict[str, Any]]] = []
    with client.stream("GET", path) as response:
        if response.status_code != 200:
            response.read()
            raise AssertionError(f"SSE {path}: expected 200, got {response.status_code}: {response.text[:500]}")
        event_name = "message"
        for line in response.iter_lines():
            if line.startswith("event: "):
                event_name = line[7:]
            elif line.startswith("data: "):
                frames.append((event_name, json.loads(line[6:])))
                if done(frames):
                    break
            elif not line:
                event_name = "message"
    return frames


def main() -> None:
    base_url, token = resolve_connection()
    assert base_url == "http://localhost:8000", "QA must use the isolated localhost stack"
    assert token and token.startswith("rt_"), "A scoped QA token must be configured"
    headers = {"Authorization": f"Bearer {token}"}
    timeout = httpx.Timeout(15, read=15)
    checks: list[str] = []

    with httpx.Client(base_url=base_url, headers=headers, timeout=timeout) as api, httpx.Client(
        base_url="http://localhost:3000", headers=headers, timeout=timeout
    ) as web:
        expect(api.get("/health"), 200, "API health")
        expect(api.get("/openapi.json"), 200, "API OpenAPI")
        expect(web.get("/health"), 200, "web health proxy")
        expect(web.get("/openapi.json"), 200, "web root OpenAPI proxy")
        expect(web.get("/api/openapi.json"), 200, "web API OpenAPI proxy")
        expect(web.get("/api/docs"), 200, "web Swagger proxy")
        checks.append("health/docs/proxies")

        auth_status = expect(api.get("/api/v1/auth/status"), 200, "bearer auth status")
        assert auth_status["authenticated"] is True and auth_status["identity"]["username"] == "qa-owner"
        for method, path, body in [
            ("POST", "/api/v1/auth/password", {"current_password": "x", "new_password": "not permitted here"}),
            ("PATCH", "/api/v1/auth/preferences", {"locale": "fr"}),
            ("POST", "/api/v1/auth/onboarding/complete", None),
            ("GET", "/api/v1/auth/tokens", None),
            ("POST", "/api/v1/projects", {"name": "Forbidden", "slug": "forbidden"}),
        ]:
            expect(api.request(method, path, json=body), 403, f"bearer boundary {path}")
        checks.append("bearer-account/project boundaries")

        project = expect(api.get(f"/api/v1/projects/{PROJECT}"), 200, "project read")
        assert project["slug"] == PROJECT and project["progress_metric_key"] == "qa_score"
        context = expect(api.get(f"/api/v1/projects/{PROJECT}/context"), 200, "project context")
        assert context["program"]["version"] >= 2 and len(context["exclusions"]) >= 3
        previous_program_version = context["program"]["version"]
        program = expect(
            api.put(
                f"/api/v1/projects/{PROJECT}/program",
                json={"content": context["program"]["content"] + "\n\nLive API matrix verified.", "actor": "permission-qa"},
            ),
            200,
            "program version",
        )
        assert program["version"] == previous_program_version + 1
        current_exclusions = expect(api.get(f"/api/v1/projects/{PROJECT}/exclusions"), 200, "read exclusions")
        exclusions = expect(
            api.put(
                f"/api/v1/projects/{PROJECT}/exclusions",
                json={"rules": context["exclusions"] + ["Do not reuse permission QA identifiers"], "actor": "permission-qa"},
            ),
            200,
            "exclusions version",
        )
        assert exclusions["version"] == current_exclusions["version"] + 1
        checks.append("project/program/exclusions context")

        experiment = expect(
            api.post(
                f"/api/v1/projects/{PROJECT}/experiments",
                json={
                    "title": "Live API matrix lifecycle",
                    "hypothesis": "The isolated PostgreSQL service preserves one claimed lifecycle and all evidence.",
                    "reasoning": "Exercise the real HTTP and reverse-proxy paths.",
                    "implementation_details": "Record synthetic metrics, events, parameters, and artifacts.",
                    "source": "qa",
                    "source_model": "codex",
                    "metric_mode": "curve",
                    "configuration": {"tags": ["permission-qa", "live-api"]},
                    "priority": 5,
                },
            ),
            201,
            "create experiment",
        )
        claimed = expect(
            api.post(
                f"/api/v1/projects/{PROJECT}/experiments/{experiment['id']}/claim",
                json={"worker_id": WORKER, "request_id": "api-matrix-claim"},
            ),
            200,
            "claim experiment",
        )
        assert claimed["lifecycle"] == "pending" and claimed["claimed_by"] == WORKER
        run_body = {
            "experiment_id": experiment["id"],
            "name": "Live API matrix run",
            "hypothesis": experiment["hypothesis"],
            "reasoning": experiment["reasoning"],
            "change_summary": "Exercised live permission-unblocked endpoints.",
            "decision_changed": "Moved environment-limited checks to an isolated PostgreSQL stack.",
            "evidence_used": [{"kind": "verification-report", "lesson": "Live authority was previously unavailable."}],
            "metric_mode": "curve",
            "configuration": {"tags": ["permission-qa", "live-api"], "matrix": True},
        }
        expect(api.post(f"/api/v1/projects/{PROJECT}/runs", json=run_body), 409, "missing claim worker")
        expect(
            api.post(f"/api/v1/projects/{PROJECT}/runs", json={**run_body, "worker_id": "wrong-worker"}),
            409,
            "mismatched claim worker",
        )
        run = expect(
            api.post(f"/api/v1/projects/{PROJECT}/runs", json={**run_body, "worker_id": WORKER}),
            201,
            "start claimed run",
        )
        run_id = run["id"]
        assert run["lifecycle"] == "running" and run["experiment_id"] == experiment["id"]
        checks.append("claim/worker/start lifecycle")

        metric_headers = {"X-Request-ID": "api-matrix-metric-1"}
        accepted = expect(
            api.post(
                f"/api/v1/runs/{run_id}/metrics",
                json={"metrics": [{"name": "qa_score", "value": 2.0, "step": 1, "context": {"phase": "initial"}}]},
                headers=metric_headers,
            ),
            202,
            "metric append",
        )
        assert accepted == {"accepted": 1, "idempotent_replay": False}
        replay = expect(
            api.post(
                f"/api/v1/runs/{run_id}/metrics",
                json={"metrics": [{"name": "qa_score", "value": 999.0, "step": 999}]},
                headers=metric_headers,
            ),
            202,
            "metric replay",
        )
        assert replay == {"accepted": 0, "idempotent_replay": True}
        event_headers = {"X-Request-ID": "api-matrix-event-1"}
        event = expect(
            api.post(
                f"/api/v1/runs/{run_id}/events",
                json={"message": "Initial live evidence", "level": "info", "event_type": "qa", "metadata": {"synthetic": True}},
                headers=event_headers,
            ),
            201,
            "event append",
        )
        event_replay = expect(
            api.post(
                f"/api/v1/runs/{run_id}/events",
                json={"message": "Must not replace the first event", "level": "error"},
                headers=event_headers,
            ),
            201,
            "event replay",
        )
        assert event_replay["id"] == event["id"] and event_replay["message"] == "Initial live evidence"
        expect(
            api.post(f"/api/v1/runs/{run_id}/parameters", json={"parameters": {"batch_size": 4, "tags": ["permission-qa", "live-api"]}}),
            202,
            "parameter upsert",
        )
        checks.append("metric/event idempotency and parameters")

        preview_bytes = ("permission qa evidence\n" * 30_000).encode()
        artifact = expect(
            api.post(
                f"/api/v1/runs/{run_id}/artifacts",
                files={"file": ("../../permission-qa.log", preview_bytes, "text/plain")},
                data={"metadata": json.dumps({"kind": "log", "synthetic": True})},
            ),
            201,
            "large text artifact",
        )
        assert artifact["name"] == "permission-qa.log"
        preview = expect(api.get(f"/api/v1/artifacts/{artifact['id']}/preview"), 200, "artifact preview")
        assert preview["truncated"] is True and len(preview["content"].encode()) == 512_000
        downloaded = expect(api.get(f"/api/v1/artifacts/{artifact['id']}/download"), 200, "artifact download")
        assert downloaded == preview_bytes
        binary = expect(
            api.post(
                f"/api/v1/runs/{run_id}/artifacts",
                files={"file": ("sample.bin", b"\x00\x01\x02", "application/octet-stream")},
                data={"metadata": "{}"},
            ),
            201,
            "binary artifact",
        )
        expect(api.get(f"/api/v1/artifacts/{binary['id']}/preview"), 415, "binary preview rejection")
        expect(
            api.post(
                f"/api/v1/runs/{run_id}/artifacts",
                files={"file": ("too-large.bin", b"x" * (10 * 1024 * 1024 + 1), "application/octet-stream")},
                data={"metadata": "{}"},
            ),
            413,
            "artifact size limit",
        )
        checks.append("artifact upload/download/preview/limits")

        inline_spec = {
            "version": 1,
            "title": "Permission QA summary",
            "datasets": {"rows": {"source": "inline", "rows": [{"label": "live", "value": 1}]}},
            "view": {"type": "card", "children": [{"type": "metric", "dataset": "rows", "field": "value", "label": "Live checks"}]},
        }
        expect(api.post(f"/api/v1/projects/{PROJECT}/visualizations/preview", json=inline_spec), 200, "RTVis inline preview")
        row_limit_spec = {
            **inline_spec,
            "title": "Too many rows",
            "datasets": {"rows": {"source": "inline", "rows": [{"value": index} for index in range(5_001)]}},
        }
        expect(api.post(f"/api/v1/projects/{PROJECT}/visualizations/preview", json=row_limit_spec), 422, "RTVis row limit")
        node: dict[str, Any] = {"type": "text", "content": "leaf"}
        for _ in range(11):
            node = {"type": "card", "children": [node]}
        depth_spec = {"version": 1, "title": "Too deep", "datasets": {}, "view": node}
        expect(api.post(f"/api/v1/projects/{PROJECT}/visualizations/preview", json=depth_spec), 422, "RTVis depth limit")
        document_spec = {
            "version": 1,
            "title": "Too large",
            "datasets": {"rows": {"source": "inline", "rows": [{"index": i, "blob": "x" * 250} for i in range(5_000)]}},
            "view": {"type": "table", "dataset": "rows", "columns": [{"key": "index", "label": "Index"}]},
        }
        expect(api.post(f"/api/v1/projects/{PROJECT}/visualizations/preview", json=document_spec), 422, "RTVis document limit")
        run_metrics_spec = {
            "version": 1,
            "title": "Live run metrics",
            "datasets": {"metrics": {"source": "runtrace", "query": "run_metrics", "filters": {"limit": 10}}},
            "view": {"type": "table", "dataset": "metrics", "columns": [{"key": "name", "label": "Metric"}, {"key": "value", "label": "Value", "format": "number"}]},
        }
        source_preview = expect(
            api.post(f"/api/v1/projects/{PROJECT}/visualizations/preview", params={"source_run_id": run_id}, json=run_metrics_spec),
            200,
            "source-bound preview",
        )
        assert source_preview["resolved_datasets"]["metrics"][0]["value"] == 2.0
        visualization = expect(
            api.post(
                f"/api/v1/projects/{PROJECT}/visualizations",
                json={"name": "Persistent live API metrics", "description": "Created by permission-unblocked QA", "source_run_id": run_id, "spec": run_metrics_spec},
            ),
            201,
            "source-bound visualization",
        )
        expect(api.delete(f"/api/v1/runs/{run_id}"), 409, "running/source run delete protection")
        exported = expect(
            api.get(f"/api/v1/projects/{PROJECT}/visualizations/{visualization['id']}/export"),
            200,
            "visualization export",
        )
        assert exported["visualization"]["spec"]["datasets"]["metrics"]["source"] == "inline"
        imported = expect(
            api.post(
                f"/api/v1/projects/{PROJECT}/visualizations/import",
                json={"document": exported, "name": "Imported portable live metrics"},
            ),
            201,
            "visualization import",
        )
        assert imported["source_run_id"] is None
        expect(api.delete(f"/api/v1/projects/{PROJECT}/visualizations/{imported['id']}"), 204, "delete imported visualization")
        checks.append("RTVis preview/source/export/import/limits")

        first_frames = sse_until(
            web,
            f"/api/v1/runs/{run_id}/stream",
            lambda frames: {kind for kind, _ in frames} >= {"metric", "event", "status"},
        )
        first_metric_id = max(frame["id"] for kind, frame in first_frames if kind == "metric")
        first_event_id = max(frame["id"] for kind, frame in first_frames if kind == "event")

        producer_error: list[BaseException] = []

        def produce_terminal_evidence() -> None:
            try:
                time.sleep(0.5)
                with httpx.Client(base_url=base_url, headers=headers, timeout=timeout) as producer:
                    expect(
                        producer.post(
                            f"/api/v1/runs/{run_id}/metrics",
                            json={"metrics": [{"name": "qa_score", "value": 1.5, "step": 2, "context": {"phase": "terminal"}}]},
                            headers={"X-Request-ID": "api-matrix-metric-2"},
                        ),
                        202,
                        "terminal metric",
                    )
                    expect(
                        producer.post(
                            f"/api/v1/runs/{run_id}/events",
                            json={"message": "Terminal live evidence", "level": "warning", "event_type": "qa"},
                            headers={"X-Request-ID": "api-matrix-event-2"},
                        ),
                        201,
                        "terminal event",
                    )
                    expect(
                        producer.post(
                            f"/api/v1/runs/{run_id}/finish",
                            json={"disposition": "kept", "result_summary": "qa_score=1.5", "conclusion": "Live API matrix passed."},
                            headers={"X-Request-ID": "api-matrix-finish"},
                        ),
                        200,
                        "finish run",
                    )
            except BaseException as exc:  # preserve producer diagnostics for the main thread
                producer_error.append(exc)

        producer_thread = threading.Thread(target=produce_terminal_evidence, daemon=True)
        producer_thread.start()
        resumed_frames = sse_until(
            web,
            f"/api/v1/runs/{run_id}/stream?after_metric_id={first_metric_id}&after_event_id={first_event_id}",
            lambda frames: any(kind == "status" and frame["lifecycle"] == "completed" for kind, frame in frames),
        )
        producer_thread.join(timeout=10)
        assert not producer_thread.is_alive() and not producer_error
        assert [frame["value"] for kind, frame in resumed_frames if kind == "metric"] == [1.5]
        assert [frame["message"] for kind, frame in resumed_frames if kind == "event"] == ["Terminal live evidence"]
        assert any(kind == "status" and frame["lifecycle"] == "completed" for kind, frame in resumed_frames)
        finish_replay = expect(
            api.post(
                f"/api/v1/runs/{run_id}/finish",
                json={"disposition": "discarded", "result_summary": "must not replace", "conclusion": "must not replace"},
                headers={"X-Request-ID": "api-matrix-finish"},
            ),
            200,
            "finish replay",
        )
        assert finish_replay["disposition"] == "kept" and finish_replay["result_summary"] == "qa_score=1.5"
        expect(api.post(f"/api/v1/runs/{run_id}/crash", json={"error_summary": "late crash"}), 409, "late crash rejection")
        checks.append("reverse-proxy SSE resume and terminal replay")

        baseline = expect(
            api.post(f"/api/v1/projects/{PROJECT}/baseline", json={"run_id": run_id, "actor": "permission-qa", "request_id": "api-matrix-baseline"}),
            200,
            "set baseline",
        )
        assert baseline["run"]["id"] == run_id
        progress = expect(api.get(f"/api/v1/projects/{PROJECT}/progress", params={"metric": "qa_score"}), 200, "progress")
        assert any(point["run_id"] == run_id and point["raw_value"] == 1.5 for point in progress["series"])
        expected_best = min(point["raw_value"] for point in progress["series"])
        assert progress["best"] == expected_best
        search = expect(
            api.post("/api/v1/search", json={"project": PROJECT, "query": "permission-unblocked", "limit": 20}),
            200,
            "keyword search",
        )
        assert any(item["id"] == run_id for item in search["results"])
        expect(api.post(f"/api/v1/runs/{run_id}/archive"), 200, "archive run")
        hidden = expect(api.post("/api/v1/search", json={"project": PROJECT, "query": "permission-unblocked", "limit": 20}), 200, "archived hidden")
        assert all(item["id"] != run_id for item in hidden["results"])
        visible = expect(
            api.post("/api/v1/search", json={"project": PROJECT, "query": "permission-unblocked", "include_archived": True, "limit": 20}),
            200,
            "archived visible",
        )
        assert any(item["id"] == run_id for item in visible["results"])
        expect(api.post(f"/api/v1/runs/{run_id}/restore"), 200, "restore run")
        dashboard = expect(api.get(f"/api/v1/projects/{PROJECT}/dashboard"), 200, "dashboard aggregate")
        assert dashboard["baseline"]["id"] == run_id and any(item["id"] == run_id for item in dashboard["history"])
        checks.append("baseline/progress/search/archive/dashboard")

        crash_run = expect(
            api.post(
                f"/api/v1/projects/{PROJECT}/runs",
                json={"name": "Expected crash replay", "hypothesis": "A synthetic failure is terminal.", "metric_mode": "scalar"},
            ),
            201,
            "create crash run",
        )
        crash_headers = {"X-Request-ID": "api-matrix-crash"}
        crashed = expect(
            api.post(f"/api/v1/runs/{crash_run['id']}/crash", json={"error_summary": "Synthetic expected failure"}, headers=crash_headers),
            200,
            "crash run",
        )
        crash_replay = expect(
            api.post(f"/api/v1/runs/{crash_run['id']}/crash", json={"error_summary": "must not replace"}, headers=crash_headers),
            200,
            "crash replay",
        )
        assert crashed["result_summary"] == crash_replay["result_summary"] == "Synthetic expected failure"
        checks.append("crash/replay")

        unused_type_key = "permission-qa-unused"
        type_spec = {
            "version": 1,
            "title": "Latest QA metrics",
            "datasets": {"metrics": {"source": "runtrace", "query": "run_metrics", "filters": {"latest_per_name": True}}},
            "view": {"type": "chart", "chart": "bar", "dataset": "metrics", "x": "name", "y": "value"},
        }
        expect(
            api.post(
                f"/api/v1/projects/{PROJECT}/result-visualizations",
                json={"key": unused_type_key, "name": "Permission QA unused", "description": "Temporary live type", "spec": type_spec},
            ),
            201,
            "create result type",
        )
        expect(api.delete(f"/api/v1/projects/{PROJECT}/result-visualizations/{unused_type_key}"), 204, "delete unused result type")
        checks.append("custom result type lifecycle")

        members = expect(api.get(f"/api/v1/auth/projects/{PROJECT}/members"), 200, "project members")
        assert any(member["identity"]["username"] == "qa-owner" and member["role"] == "owner" for member in members)
        tags = expect(api.get(f"/api/v1/projects/{PROJECT}/tags"), 200, "tag registry")
        assert {tag["name"] for tag in tags} >= {"permission-qa", "live-api"}
        checks.append("membership and auto-tag registry")

    with httpx.Client(base_url=base_url, timeout=timeout) as anonymous:
        last_status = None
        for _ in range(11):
            last_status = anonymous.post(
                "/api/v1/auth/login",
                json={"username": "rate-limit-probe", "password": "always-wrong"},
            ).status_code
        assert last_status == 429
        checks.append("live login throttling")

    print(json.dumps({"status": "passed", "checks": checks, "count": len(checks)}, indent=2))


if __name__ == "__main__":
    main()
