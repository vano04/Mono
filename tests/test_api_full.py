from sqlalchemy import func, select

from runtrace_api.database import SessionLocal
from runtrace_api.models import AuditEvent


def test_project_creation_initializes_context_and_lists_project(fresh_database):
    created = fresh_database.post("/api/v1/projects", json={"name": "Compiler Optimizer", "slug": "compiler-optimizer", "description": "Compile faster", "repository_url": "https://github.com/example/compiler-optimizer"})
    assert created.status_code == 201
    assert fresh_database.post("/api/v1/projects", json={"name": "Duplicate", "slug": "compiler-optimizer"}).status_code == 409
    assert fresh_database.get("/health").json()["status"] == "ok"
    assert fresh_database.get("/api/v1/projects/compiler-optimizer").json()["description"] == "Compile faster"
    updated = fresh_database.patch(
        "/api/v1/projects/compiler-optimizer",
        json={"description": "Reduce compile time without changing output", "repository_url": "https://github.com/example/compiler-optimizer-v2"},
    )
    assert updated.status_code == 200
    assert updated.json()["description"] == "Reduce compile time without changing output"
    assert updated.json()["repository_url"] == "https://github.com/example/compiler-optimizer-v2"
    assert "compiler-optimizer" in {project["slug"] for project in fresh_database.get("/api/v1/projects").json()}
    assert fresh_database.get("/api/v1/projects/compiler-optimizer/program").json() == {
        "content": "# Compiler Optimizer\n", "version": 1, "created_at": fresh_database.get("/api/v1/projects/compiler-optimizer/program").json()["created_at"]
    }
    assert fresh_database.get("/api/v1/projects/compiler-optimizer/exclusions").json()["rules"] == []


def test_complete_experiment_and_run_lifecycle(fresh_database):
    proposed = fresh_database.post("/api/v1/projects/dense-optimizer/experiments", json={"title": "New cap", "hypothesis": "It is faster", "metric_mode": "scalar"})
    assert proposed.status_code == 201
    display_id = proposed.json()["display_id"]
    assert display_id in {item["display_id"] for item in fresh_database.get("/api/v1/projects/dense-optimizer/experiments").json()}

    claimed = fresh_database.post(f"/api/v1/projects/dense-optimizer/experiments/{display_id}/claim", json={"worker_id": "qa-worker"})
    assert claimed.json()["lifecycle"] == "pending"
    assert fresh_database.post(f"/api/v1/projects/dense-optimizer/experiments/{display_id}/claim", json={"worker_id": "other"}).status_code == 409

    hijacked = fresh_database.post(
        "/api/v1/projects/dense-optimizer/runs",
        json={"name": "Wrong worker", "experiment_id": display_id, "worker_id": "other"},
    )
    assert hijacked.status_code == 409
    assert fresh_database.post(
        "/api/v1/projects/dense-optimizer/runs",
        json={"name": "Missing worker", "experiment_id": display_id},
    ).status_code == 409

    run = fresh_database.post("/api/v1/projects/dense-optimizer/runs", json={"name": "New cap run", "experiment_id": display_id, "worker_id": "qa-worker", "configuration": {"total_steps": 2}})
    assert run.status_code == 201
    run_id = run.json()["id"]
    assert fresh_database.post(f"/api/v1/runs/{run_id}/parameters", json={"parameters": {"rank": 4}}).json()["accepted"] == 1
    assert fresh_database.post(f"/api/v1/runs/{run_id}/parameters", json={"parameters": {"rank": 8}}).json()["accepted"] == 1
    event_headers = {"X-Request-ID": "event-1"}
    event = fresh_database.post(
        f"/api/v1/runs/{run_id}/events",
        json={"message": "Started", "event_type": "status"},
        headers=event_headers,
    )
    event_replay = fresh_database.post(
        f"/api/v1/runs/{run_id}/events",
        json={"message": "Duplicate", "event_type": "status"},
        headers=event_headers,
    )
    assert event.status_code == 201
    assert event_replay.json() == event.json()
    first = fresh_database.post(f"/api/v1/runs/{run_id}/metrics", json={"metrics": [{"name": "score", "value": 2.0, "step": 1}]}, headers={"X-Request-ID": "metrics-1"})
    replay = fresh_database.post(f"/api/v1/runs/{run_id}/metrics", json={"metrics": [{"name": "score", "value": 99.0}]}, headers={"X-Request-ID": "metrics-1"})
    assert first.json()["accepted"] == 1
    assert replay.json() == {"accepted": 0, "idempotent_replay": True}
    detail = fresh_database.get(f"/api/v1/runs/{run_id}").json()
    assert detail["parameters"] == {"rank": 8}
    assert detail["metrics"]["score"]["latest"] == 2.0
    assert detail["events"][0]["message"] == "Started"

    finish_headers = {"X-Request-ID": "finish-scope-proof"}
    finished = fresh_database.post(
        f"/api/v1/runs/{run_id}/finish",
        json={"disposition": "kept", "result_summary": "score 2", "conclusion": "Keep it"},
        headers=finish_headers,
    )
    assert finished.json()["lifecycle"] == "completed"
    finish_replay = fresh_database.post(
        f"/api/v1/runs/{run_id}/finish",
        json={"disposition": "discarded", "result_summary": "must not replace", "conclusion": "must not replace"},
        headers=finish_headers,
    )
    assert finish_replay.json()["result_summary"] == "score 2"
    terminal_state = fresh_database.get(f"/api/v1/runs/{run_id}").json()
    assert fresh_database.post(f"/api/v1/runs/{run_id}/metrics", json={"metrics": [{"name": "score", "value": 3.0}]}).status_code == 409
    terminal_metric_replay = fresh_database.post(
        f"/api/v1/runs/{run_id}/metrics",
        json={"metrics": [{"name": "score", "value": 99.0}]},
        headers={"X-Request-ID": "metrics-1"},
    )
    assert terminal_metric_replay.json() == {"accepted": 0, "idempotent_replay": True}
    assert fresh_database.post(f"/api/v1/runs/{run_id}/crash", json={"error_summary": "late crash report"}).status_code == 409
    after_rejected_crash = fresh_database.get(f"/api/v1/runs/{run_id}").json()
    for field in ("lifecycle", "disposition", "result_summary", "conclusion", "finished_at"):
        assert after_rejected_crash[field] == terminal_state[field]

    other_finished = fresh_database.post(
        "/api/v1/projects/dense-optimizer/runs",
        json={"name": "Finish idempotency scope"},
    ).json()
    assert fresh_database.post(
        f"/api/v1/runs/{other_finished['id']}/finish",
        json={"disposition": "discarded", "result_summary": "separate finish", "conclusion": "separate run"},
        headers=finish_headers,
    ).status_code == 200
    assert fresh_database.post(
        f"/api/v1/runs/{other_finished['id']}/finish",
        json={"disposition": "kept", "result_summary": "must not replace", "conclusion": "must not replace"},
        headers=finish_headers,
    ).json()["result_summary"] == "separate finish"
    with SessionLocal() as session:
        audit_count = session.scalar(select(func.count()).select_from(AuditEvent).where(
            AuditEvent.action == "run.completed",
            AuditEvent.request_id == "finish-scope-proof",
        ))
    assert audit_count == 2

    other_run = fresh_database.post(
        "/api/v1/projects/dense-optimizer/runs",
        json={"name": "Crash idempotency scope"},
    ).json()
    cross_run_metric = fresh_database.post(
        f"/api/v1/runs/{other_run['id']}/metrics",
        json={"metrics": [{"name": "score", "value": 7.0}]},
        headers={"X-Request-ID": "metrics-1"},
    )
    assert cross_run_metric.json() == {"accepted": 1, "idempotent_replay": False}
    cross_run_event = fresh_database.post(
        f"/api/v1/runs/{other_run['id']}/events",
        json={"message": "Separate run", "event_type": "status"},
        headers=event_headers,
    )
    assert cross_run_event.status_code == 201
    assert cross_run_event.json()["id"] != event.json()["id"]
    idempotency_headers = {"X-Request-ID": "crash-scope-proof"}
    assert fresh_database.post(
        f"/api/v1/runs/{other_run['id']}/crash",
        json={"error_summary": "synthetic failure"},
        headers=idempotency_headers,
    ).status_code == 200
    assert fresh_database.post(
        f"/api/v1/runs/{other_run['id']}/crash",
        json={"error_summary": "synthetic failure"},
        headers=idempotency_headers,
    ).status_code == 200
    assert fresh_database.post(
        f"/api/v1/runs/{run_id}/crash",
        json={"error_summary": "wrong run retry"},
        headers=idempotency_headers,
    ).status_code == 409
    assert fresh_database.get("/api/v1/projects/dense-optimizer/dashboard").status_code == 200


def test_run_archive_restore_delete_and_crash(fresh_database):
    created = fresh_database.post("/api/v1/projects/dense-optimizer/runs", json={"name": "Crash test"}).json()
    run_id = created["id"]
    assert fresh_database.delete(f"/api/v1/runs/{run_id}").status_code == 409
    crashed = fresh_database.post(f"/api/v1/runs/{run_id}/crash", json={"error_summary": "out of memory"})
    assert crashed.json()["lifecycle"] == "crashed"
    assert fresh_database.post(f"/api/v1/runs/{run_id}/archive").json()["archived_at"]
    assert run_id not in {run["id"] for run in fresh_database.get("/api/v1/projects/dense-optimizer/runs").json()}
    assert fresh_database.post(f"/api/v1/runs/{run_id}/restore").json()["archived_at"] is None
    assert fresh_database.delete(f"/api/v1/runs/{run_id}").status_code == 204
    assert fresh_database.get(f"/api/v1/runs/{run_id}").status_code == 404


def test_deleting_current_baseline_clears_project_reference(fresh_database):
    context = fresh_database.get("/api/v1/projects/dense-optimizer/context").json()
    assert context["baseline"]["id"] == "run_168"

    assert fresh_database.delete("/api/v1/runs/RUN-168").status_code == 204

    context = fresh_database.get("/api/v1/projects/dense-optimizer/context")
    dashboard = fresh_database.get("/api/v1/projects/dense-optimizer/dashboard")
    assert context.status_code == 200
    assert dashboard.status_code == 200
    assert context.json()["baseline"] is None
    assert dashboard.json()["baseline"] is None


def test_artifact_validation_search_variants_and_settings(fresh_database):
    run_id = fresh_database.post("/api/v1/projects/dense-optimizer/runs", json={"name": "Artifact validation"}).json()["id"]
    invalid = fresh_database.post(f"/api/v1/runs/{run_id}/artifacts", files={"file": ("data.txt", b"x", "text/plain")}, data={"metadata": "not-json"})
    assert invalid.status_code == 400
    assert fresh_database.get("/api/v1/projects/dense-optimizer/search?q=spectral").json()["count"] > 0
    assert fresh_database.post("/api/v1/search", json={"project": "dense-optimizer", "query": "spectral", "limit": 2}).json()["count"] <= 2
    settings = fresh_database.get("/api/v1/projects/dense-optimizer/settings").json()
    assert settings["metric_name"] == "validation_loss"
    assert "validation_loss" in settings["available_metrics"]


def test_tag_filters_and_text_artifact_preview(fresh_database):
    run_id = fresh_database.post(
        "/api/v1/projects/dense-optimizer/runs",
        json={"name": "Tagged completed run", "configuration": {"tags": ["nightly"]}},
    ).json()["id"]
    fresh_database.post(
        f"/api/v1/runs/{run_id}/metrics",
        json={"metrics": [{"name": "validation_loss", "value": 3.1, "step": 3350}]},
    )
    fresh_database.post(f"/api/v1/runs/{run_id}/finish", json={"disposition": "kept"})

    included = fresh_database.get("/api/v1/projects/dense-optimizer/search?include_tag=nightly&limit=50").json()["results"]
    assert {result["id"] for result in included} == {run_id}
    assert included[0]["tags"] == ["nightly"]
    assert fresh_database.get("/api/v1/projects/dense-optimizer/progress?include_tag=nightly").json()["series"][0]["final_step"] == 3350
    assert fresh_database.get("/api/v1/projects/dense-optimizer/progress?exclude_tag=early%20stop").json()["series"][0]["run_id"] == run_id

    uploaded = fresh_database.post(
        f"/api/v1/runs/{run_id}/artifacts",
        files={"file": ("training.log", b"step=3350 loss=3.1", "text/plain")},
        data={"metadata": '{"kind":"log"}'},
    ).json()
    preview = fresh_database.get(f"/api/v1/artifacts/{uploaded['id']}/preview")
    assert preview.status_code == 200
    assert preview.json()["content"] == "step=3350 loss=3.1"


def test_imported_autoresearch_runtime_fallback_tags(fresh_database):
    early_id = fresh_database.post(
        "/api/v1/projects/dense-optimizer/runs",
        json={"name": "Imported early run", "configuration": {"source_file": "results.tsv", "autoresearch_status": "discard"}},
    ).json()["id"]
    fresh_database.post(f"/api/v1/runs/{early_id}/metrics", json={"metrics": [
        {"name": "validation_loss", "value": 4.0}, {"name": "train_time_s", "value": 900},
    ]})
    fresh_database.post(f"/api/v1/runs/{early_id}/finish", json={"disposition": "discarded"})
    long_id = fresh_database.post(
        "/api/v1/projects/dense-optimizer/runs",
        json={"name": "Imported extended run", "configuration": {"source_file": "results.tsv", "autoresearch_status": "keep"}},
    ).json()["id"]
    fresh_database.post(f"/api/v1/runs/{long_id}/metrics", json={"metrics": [
        {"name": "validation_loss", "value": 3.0}, {"name": "train_time_s", "value": 8000},
    ]})
    fresh_database.post(f"/api/v1/runs/{long_id}/finish", json={"disposition": "kept"})

    assert fresh_database.get(f"/api/v1/runs/{early_id}").json()["tags"] == ["early stop"]
    assert fresh_database.get(f"/api/v1/runs/{long_id}").json()["tags"] == ["long run"]


def test_tag_registry_crud_renames_rule_tags_and_removes_explicit_uses(fresh_database):
    tags = fresh_database.get("/api/v1/projects/dense-optimizer/tags").json()
    early = next(tag for tag in tags if tag["name"] == "early stop")
    renamed = fresh_database.patch(f"/api/v1/projects/dense-optimizer/tags/{early['id']}", json={"name": "short run"})
    assert renamed.status_code == 200
    assert renamed.json()["rule_key"] == "autoresearch_early_stop"

    inferred_id = fresh_database.post(
        "/api/v1/projects/dense-optimizer/runs",
        json={"name": "Short", "configuration": {"source_file": "results.tsv", "autoresearch_status": "discard"}},
    ).json()["id"]
    fresh_database.post(f"/api/v1/runs/{inferred_id}/metrics", json={"metrics": [{"name": "train_time_s", "value": 900}]})
    assert fresh_database.get(f"/api/v1/runs/{inferred_id}").json()["tags"] == ["short run"]

    created = fresh_database.post("/api/v1/projects/dense-optimizer/tags", json={"name": "nightly"})
    assert created.status_code == 201
    run_id = fresh_database.post("/api/v1/projects/dense-optimizer/runs", json={"name": "Tagged", "configuration": {"tags": ["nightly"]}}).json()["id"]
    assert fresh_database.delete(f"/api/v1/projects/dense-optimizer/tags/{created.json()['id']}").status_code == 204
    assert fresh_database.get(f"/api/v1/runs/{run_id}").json()["tags"] == []


def test_experiment_delete_and_claim_next(fresh_database):
    claimed = fresh_database.post("/api/v1/projects/dense-optimizer/experiments/claim", json={"worker_id": "next-worker"})
    assert claimed.status_code == 200
    assert claimed.json()["display_id"] == "EXP-021"
    assert fresh_database.delete("/api/v1/projects/dense-optimizer/experiments/EXP-023").status_code == 204
    assert "EXP-023" not in {item["display_id"] for item in fresh_database.get("/api/v1/projects/dense-optimizer/experiments?include_archived=true").json()}


def test_completed_run_stream_emits_metrics_and_terminal_status(fresh_database):
    response = fresh_database.get("/api/v1/runs/RUN-168/stream")
    assert response.status_code == 200
    assert "event: metric" in response.text
    assert 'event: status' in response.text
    assert '"lifecycle": "completed"' in response.text


def test_run_stream_can_resume_after_known_metric_and_event_ids(fresh_database):
    run = fresh_database.get("/api/v1/runs/RUN-168").json()
    metric_id = max(point["id"] for series in run["metrics"].values() for point in series["points"])
    event_id = max((event["id"] for event in run["events"]), default=0)

    response = fresh_database.get(
        f"/api/v1/runs/RUN-168/stream?after_metric_id={metric_id}&after_event_id={event_id}"
    )

    assert response.status_code == 200
    assert "event: metric" not in response.text
    assert "event: event" not in response.text
    assert "event: status" in response.text


def test_run_stream_rejects_ambiguous_cross_project_display_id(fresh_database):
    first = fresh_database.post(
        "/api/v1/projects/dense-optimizer/runs",
        json={"name": "Dense duplicate display"},
    ).json()
    second = fresh_database.post(
        "/api/v1/projects/flash-attention-kernel/runs",
        json={"name": "Flash duplicate display"},
    ).json()
    assert first["display_id"] == second["display_id"]

    response = fresh_database.get(f"/api/v1/runs/{first['display_id']}/stream")
    assert response.status_code == 409
    assert response.json()["detail"] == "Run display ID is ambiguous; use the full run ID"
