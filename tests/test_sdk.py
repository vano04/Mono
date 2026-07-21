import httpx
import pytest

from mono.client import Mono


def test_sdk_buffers_metrics_during_network_outage(fresh_database):
    client = Mono(base_url="http://127.0.0.1:1", strict=False, timeout=0.01)
    result = client.request("POST", "/api/v1/runs/missing/metrics", {"metrics": [{"name": "loss", "value": 1.0}]}, buffer=True)
    assert result is None
    assert len(client._buffer) == 1


@pytest.mark.parametrize(("path", "payload"), [
    ("metrics", {"metrics": [{"name": "loss", "value": 1.0}]}),
    ("events", {"message": "late event"}),
    ("parameters", {"parameters": {"rank": 4}}),
])
def test_strict_sdk_does_not_buffer_rejected_writes(fresh_database, path, payload):
    client = Mono(base_url="http://testserver", strict=True)
    client.client.close()
    client.client = fresh_database

    with pytest.raises(httpx.HTTPStatusError):
        client.request(
            "POST",
            f"/api/v1/runs/missing/{path}",
            payload,
            buffer=True,
        )
    assert len(client._buffer) == 0


def test_best_effort_sdk_drops_permanently_rejected_buffered_writes(fresh_database):
    client = Mono(base_url="http://testserver", strict=False)
    client.client.close()
    client.client = fresh_database

    with pytest.warns(RuntimeWarning, match="rejected"):
        result = client.request(
            "POST",
            "/api/v1/runs/missing/metrics",
            {"metrics": [{"name": "loss", "value": 1.0}]},
            buffer=True,
        )
    assert result is None
    assert len(client._buffer) == 0

    client._buffer.append((
        "POST",
        "/api/v1/runs/missing/metrics",
        {"metrics": [{"name": "loss", "value": 1.0}]},
        "rejected-request",
    ))
    with pytest.warns(RuntimeWarning, match="discarded rejected"):
        assert client.flush() == 0
    assert len(client._buffer) == 0


def test_strict_sdk_flush_retains_and_raises_rejected_buffered_write(fresh_database):
    client = Mono(base_url="http://testserver", strict=True)
    client.client.close()
    client.client = fresh_database
    client._buffer.append((
        "POST",
        "/api/v1/runs/missing/metrics",
        {"metrics": [{"name": "loss", "value": 1.0}]},
        "strict-rejected-request",
    ))

    with pytest.raises(httpx.HTTPStatusError):
        client.flush()
    assert len(client._buffer) == 1
    with pytest.warns(RuntimeWarning, match="could not flush buffered writes during shutdown"):
        client._flush_at_exit()
    assert len(client._buffer) == 1
    client._buffer.clear()


def test_strict_sdk_flush_raises_transport_failure_and_shutdown_warns():
    client = Mono(base_url="http://127.0.0.1:1", strict=True, timeout=0.01)
    client._buffer.append((
        "POST",
        "/api/v1/runs/missing/metrics",
        {"metrics": [{"name": "loss", "value": 1.0}]},
        "strict-transport-request",
    ))

    with pytest.raises(httpx.RequestError):
        client.flush()
    assert len(client._buffer) == 1
    with pytest.warns(RuntimeWarning, match="could not flush buffered writes during shutdown"):
        client._flush_at_exit()
    assert len(client._buffer) == 1
    client._buffer.clear()
    client.client.close()


def test_5xx_buffering_respects_strict_mode_and_never_evicts_when_full():
    def unavailable(request):
        return httpx.Response(503, json={"detail": "unavailable"}, request=request)

    best_effort = Mono(base_url="http://testserver", strict=False)
    best_effort.client.close()
    best_effort.client = httpx.Client(base_url="http://testserver", transport=httpx.MockTransport(unavailable))
    with pytest.warns(RuntimeWarning, match="buffered"):
        best_effort.request("POST", "/write", {"value": 1}, buffer=True, request_id="first")
    for index in range(1, best_effort._buffer.maxlen):
        best_effort._queue_request("POST", "/write", {"value": index}, f"queued-{index}")
    with pytest.raises(BufferError, match="buffer is full"):
        best_effort.request("POST", "/write", {"value": "overflow"}, buffer=True)
    assert len(best_effort._buffer) == best_effort._buffer.maxlen
    assert best_effort._buffer[0][3] == "first"
    best_effort._buffer.clear()
    best_effort.client.close()

    strict = Mono(base_url="http://testserver", strict=True)
    strict.client.close()
    strict.client = httpx.Client(base_url="http://testserver", transport=httpx.MockTransport(unavailable))
    with pytest.raises(httpx.HTTPStatusError):
        strict.request("POST", "/write", {"value": 1}, buffer=True)
    assert len(strict._buffer) == 0
    strict.client.close()


def test_terminal_flushes_buffered_evidence_before_finishing(fresh_database):
    client = Mono(base_url="http://testserver", strict=True)
    client.client.close()
    client.client = fresh_database
    project = client.create_project("Buffered SDK", "buffered-sdk")
    tracked = client.run(project["slug"], "Buffered evidence")
    tracked.__enter__()
    assert tracked.id

    live_client = client.client
    client.client = httpx.Client(base_url="http://127.0.0.1:1", timeout=0.01)
    with pytest.warns(RuntimeWarning, match="buffered"):
        tracked.log_metric("loss", 1.25, step=3)
    client.client.close()
    client.client = live_client

    tracked.finish("kept", "loss=1.25", "Evidence flushed first")

    assert len(client._buffer) == 0
    detail = fresh_database.get(f"/api/v1/runs/{tracked.id}").json()
    assert detail["lifecycle"] == "completed"
    assert detail["metrics"]["loss"]["latest"] == 1.25


def test_terminal_is_queued_after_evidence_during_persistent_outage(fresh_database):
    client = Mono(base_url="http://testserver", strict=True)
    client.client.close()
    client.client = fresh_database
    project = client.create_project("Persistent outage", "persistent-outage")
    tracked = client.run(project["slug"], "Queued terminal")
    tracked.__enter__()
    assert tracked.id

    live_client = client.client
    client.client = httpx.Client(base_url="http://127.0.0.1:1", timeout=0.01)
    with pytest.warns(RuntimeWarning, match="buffered"):
        tracked.log_metric("loss", 2.5)
    with pytest.warns(RuntimeWarning, match="buffered"):
        with pytest.raises(RuntimeError, match="terminal finish update behind pending evidence"):
            tracked.finish("kept", "loss=2.5")
    assert [item[1].rsplit("/", 1)[-1] for item in client._buffer] == ["metrics", "finish"]

    client.client.close()
    client.client = live_client
    assert client.flush() == 2
    assert len(client._buffer) == 0
    detail = fresh_database.get(f"/api/v1/runs/{tracked.id}").json()
    assert detail["lifecycle"] == "completed"
    assert detail["metrics"]["loss"]["latest"] == 2.5


def test_manual_abort_is_not_repeated_by_context_exit(fresh_database):
    client = Mono(base_url="http://testserver", strict=True)
    client.client.close()
    client.client = fresh_database
    project = client.create_project("Abort once", "abort-once")

    with pytest.raises(ValueError, match="child failed"):
        with client.run(project["slug"], "Abort once") as tracked:
            tracked.abort("exit 17")
            raise ValueError("child failed")

    detail = fresh_database.get(f"/api/v1/runs/{tracked.id}").json()
    assert detail["lifecycle"] == "crashed"
    assert detail["result_summary"] == "exit 17"


def test_sdk_covers_project_search_run_logging_and_artifacts(fresh_database, tmp_path):
    client = Mono(base_url="http://testserver", strict=True)
    client.client.close()
    client.client = fresh_database

    project = client.create_project("SDK Project", "sdk-project", "SDK coverage")
    assert project["slug"] == "sdk-project"
    assert client.search("sdk-project", "nothing")["count"] == 0

    artifact_path = tmp_path / "result.txt"
    artifact_path.write_text("result")
    with client.run("sdk-project", "Tracked SDK run", "SDK writes all data", tags=["sdk"], configuration={"total_steps": 1}) as tracked:
        assert tracked.id
        tracked.log_metric("score", 4.2, step=1)
        tracked.log_metrics({"latency": 8.0, "memory": 2.0}, step=1)
        tracked.log_param("rank", 4)
        tracked.log_params({"batch": 2})
        tracked.log_event("Measured", event_type="evaluation", metadata={"ok": True})
        tracked.log_reasoning("Evidence supports keeping it")
        tracked.set_tags(["sdk", "kept"])
        tracked.link_run("RUN-168", "baseline")
        artifact = tracked.log_artifact(str(artifact_path), metadata={"kind": "result"})
        assert artifact["name"] == "result.txt"
        tracked.log_text("stdout.log", "training complete")
        tracked.log_config({"learning_rate": 0.01})
        tracked.finish("success", "score 4.2", "SDK flow works")

    detail = fresh_database.get(f"/api/v1/runs/{tracked.id}").json()
    assert detail["lifecycle"] == "completed"
    assert detail["disposition"] == "kept"
    assert detail["metrics"]["score"]["latest"] == 4.2
    assert detail["parameters"]["tags"] == ["sdk", "kept"]
    assert detail["parameters"]["learning_rate"] == 0.01
    assert len(detail["events"]) == 3
    assert detail["artifacts"][0]["metadata"] == {"kind": "result"}
    assert {artifact["metadata"]["kind"] for artifact in detail["artifacts"]} == {"result", "log", "config"}


def test_sdk_context_manager_crashes_run_on_exception(fresh_database):
    client = Mono(base_url="http://testserver", strict=True)
    client.client.close()
    client.client = fresh_database
    try:
        with client.run("dense-optimizer", "Expected crash") as tracked:
            raise ValueError("boom")
    except ValueError:
        pass
    detail = fresh_database.get(f"/api/v1/runs/{tracked.id}").json()
    assert detail["lifecycle"] == "crashed"
    assert detail["result_summary"] == "boom"


def test_sdk_attaches_to_mono_run_id_without_creating_a_duplicate(fresh_database, monkeypatch):
    client = Mono(base_url="http://testserver", strict=True)
    client.client.close()
    client.client = fresh_database
    created = fresh_database.post(
        "/api/v1/projects/dense-optimizer/runs",
        json={"name": "Created by MCP", "hypothesis": "One execution has one run"},
    ).json()
    monkeypatch.setenv("MONO_RUN_ID", created["id"])

    with client.run("dense-optimizer", "SDK should attach") as tracked:
        assert tracked.id == created["id"]
        tracked.log_metric("loss", 3.1)
        tracked.finish("success", "loss 3.1", "Attached without duplication")

    runs = fresh_database.get("/api/v1/projects/dense-optimizer/runs").json()
    assert len([run for run in runs if run["id"] == created["id"]]) == 1
    detail = fresh_database.get(f"/api/v1/runs/{created['id']}").json()
    assert detail["metrics"]["loss"]["latest"] == 3.1
