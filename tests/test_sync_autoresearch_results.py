import argparse
import asyncio
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


SPEC = importlib.util.spec_from_file_location(
    "sync_autoresearch_results",
    Path(__file__).parents[1] / "scripts" / "sync_autoresearch_results.py",
)
assert SPEC and SPEC.loader
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)


def synthetic_row(source_row: int) -> dict:
    return {
        "commit": "abc123",
        "config": "demo.py",
        "val_loss": 1.25,
        "train_time_s": 4.0,
        "status": "keep",
        "description": "synthetic import",
        "source_row": source_row,
    }


def test_importer_rejects_unsupported_status_before_dispatch(tmp_path):
    path = tmp_path / "results.tsv"
    path.write_text(
        "commit\tconfig\tval_loss\ttrain_time_s\tstatus\tdescription\n"
        "abc123\tdemo.py\t1.25\t4.0\tretry\tunsupported status\n"
    )

    with pytest.raises(ValueError, match="row 1 has unsupported status 'retry'"):
        sync.read_rows(path)


@pytest.mark.parametrize(("source_row", "transport"), [(1, "http"), (2, "python")])
def test_importer_propagates_resolved_authentication(monkeypatch, tmp_path, source_row, transport):
    captured: dict = {"syncs": []}

    class FakeHttpClient:
        def __init__(self, **kwargs):
            captured["http_client"] = kwargs

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    monkeypatch.setattr(sync, "read_rows", lambda _path: [synthetic_row(source_row)])
    monkeypatch.setattr(sync, "resolve_connection", lambda _base_url: ("https://trace.example", "rt_synthetic"))
    monkeypatch.setattr(sync.httpx, "Client", FakeHttpClient)
    monkeypatch.setattr(sync, "existing_source_rows", lambda _client, _project: set())
    monkeypatch.setattr(sync, "sync_http", lambda _client, project, row: captured["syncs"].append(("http", project, row["source_row"])))
    monkeypatch.setattr(sync, "sync_python", lambda base_url, api_token, project, row: captured["syncs"].append(("python", base_url, api_token, project, row["source_row"])))

    args = argparse.Namespace(
        tsv=tmp_path / "results.tsv",
        project="demo-project",
        base_url=None,
        transports={transport},
    )
    asyncio.run(sync.run(args))

    assert captured["http_client"]["base_url"] == "https://trace.example"
    assert captured["http_client"]["headers"] == {"Authorization": "Bearer rt_synthetic"}
    if transport == "http":
        assert captured["syncs"] == [("http", "demo-project", 1)]
    else:
        assert captured["syncs"] == [("python", "https://trace.example", "rt_synthetic", "demo-project", 2)]


def test_mcp_import_preserves_canonical_run_fields():
    calls: list[tuple[str, dict]] = []

    class FakeSession:
        async def call_tool(self, name, arguments):
            calls.append((name, arguments))
            result = {"id": "run_mcp_1"} if name == "create_run" else {}
            return SimpleNamespace(isError=False, structuredContent={"result": result}, content=[])

    run_id = asyncio.run(sync.sync_mcp(FakeSession(), "demo-project", synthetic_row(3)))

    assert run_id == "run_mcp_1"
    create_call = calls[0]
    assert create_call == ("create_run", {
        "project": "demo-project",
        "name": "demo.py",
        "hypothesis": "synthetic import",
        "change_summary": "Autoresearch configuration demo.py",
        "git_commit": "abc123",
        "metric_mode": "scalar",
        "configuration": {
            "config_path": "demo.py",
            "autoresearch_status": "keep",
            "source_file": "results.tsv",
            "source_row": 3,
            "sync_transport": "mcp",
        },
    })


def test_existing_source_rows_recovers_incomplete_import_before_retry():
    posts: list[tuple[str, dict]] = []
    gets: list[str] = []

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    class FakeClient:
        def get(self, path):
            gets.append(path)
            return FakeResponse([
                {"id": "run_done", "lifecycle": "completed", "configuration": {"source_file": "results.tsv", "source_row": 1, "autoresearch_status": "keep"}},
                {"id": "run_partial", "lifecycle": "running", "configuration": {"source_file": "results.tsv", "source_row": 2, "autoresearch_status": "keep"}},
                {"id": "run_recovered", "lifecycle": "crashed", "result_summary": sync.IMPORT_FAILURE_SUMMARY, "configuration": {"source_file": "results.tsv", "source_row": 3, "autoresearch_status": "keep"}},
                {"id": "run_source_crash", "lifecycle": "crashed", "hypothesis": "expected source crash", "result_summary": "expected source crash", "configuration": {"source_file": "results.tsv", "source_row": 4, "autoresearch_status": "crash"}},
                {"id": "run_python_failure", "lifecycle": "crashed", "result_summary": "HTTP 422", "configuration": {"source_file": "results.tsv", "source_row": 5, "autoresearch_status": "keep"}},
                {"id": "run_python_failure_for_crash_row", "lifecycle": "crashed", "hypothesis": "expected source crash", "result_summary": "HTTP 422", "configuration": {"source_file": "results.tsv", "source_row": 6, "autoresearch_status": "crash"}},
                {"id": "run_empty_python_source_crash", "lifecycle": "crashed", "hypothesis": "", "result_summary": "Run aborted", "configuration": {"source_file": "results.tsv", "source_row": 7, "autoresearch_status": "crash", "sync_transport": "python"}},
            ])

        def post(self, path, json):
            posts.append((path, json))
            return FakeResponse({})

    assert sync.existing_source_rows(FakeClient(), "demo-project") == {1, 4, 7}
    assert gets == ["/api/v1/projects/demo-project/runs?include_archived=true"]
    assert posts == [(
        "/api/v1/runs/run_partial/crash",
        {"error_summary": sync.IMPORT_FAILURE_SUMMARY},
    )]


def test_http_import_crashes_run_when_post_create_step_fails():
    posts: list[str] = []

    class FakeResponse:
        def __init__(self, payload=None, failure=False):
            self.payload = payload or {}
            self.failure = failure

        def raise_for_status(self):
            if self.failure:
                raise RuntimeError("synthetic metric failure")

        def json(self):
            return self.payload

    class FakeClient:
        def post(self, path, json):
            posts.append(path)
            if path.endswith("/runs"):
                return FakeResponse({"id": "run_partial"})
            if path.endswith("/metrics"):
                return FakeResponse(failure=True)
            return FakeResponse()

    with pytest.raises(RuntimeError, match="synthetic metric failure"):
        sync.sync_http(FakeClient(), "demo-project", synthetic_row(1))
    assert posts == [
        "/api/v1/projects/demo-project/runs",
        "/api/v1/runs/run_partial/metrics",
        "/api/v1/runs/run_partial/crash",
    ]


def test_mcp_import_crashes_run_when_post_create_step_fails():
    calls: list[str] = []

    class FakeSession:
        async def call_tool(self, name, _arguments):
            calls.append(name)
            if name == "create_run":
                return SimpleNamespace(isError=False, structuredContent={"result": {"id": "run_partial"}}, content=[])
            if name == "log_metric":
                return SimpleNamespace(isError=True, structuredContent=None, content=["synthetic metric failure"])
            return SimpleNamespace(isError=False, structuredContent={"result": {}}, content=[])

    with pytest.raises(RuntimeError, match="synthetic metric failure"):
        asyncio.run(sync.sync_mcp(FakeSession(), "demo-project", synthetic_row(3)))
    assert calls == ["create_run", "log_metric", "crash_run"]


def test_importer_propagates_resolved_authentication_to_mcp_child(monkeypatch, tmp_path):
    import mcp
    import mcp.client.stdio as mcp_stdio

    captured: dict = {}

    class FakeHttpClient:
        def __init__(self, **kwargs):
            captured["http_client"] = kwargs

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    class FakeServerParameters:
        def __init__(self, *, command, args, env):
            captured["server"] = {"command": command, "args": args, "env": env}

    class FakeStdio:
        async def __aenter__(self):
            return "read", "write"

        async def __aexit__(self, *_args):
            return None

    class FakeClientSession:
        def __init__(self, _read, _write):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def initialize(self):
            captured["initialized"] = True

    async def fake_sync_mcp(_session, project, row):
        captured["sync"] = (project, row["source_row"])

    monkeypatch.setattr(sync, "read_rows", lambda _path: [synthetic_row(3)])
    monkeypatch.setattr(sync, "resolve_connection", lambda _base_url: ("https://trace.example", "rt_synthetic"))
    monkeypatch.setattr(sync.httpx, "Client", FakeHttpClient)
    monkeypatch.setattr(sync, "existing_source_rows", lambda _client, _project: set())
    monkeypatch.setattr(sync, "sync_mcp", fake_sync_mcp)
    monkeypatch.setattr(mcp, "StdioServerParameters", FakeServerParameters)
    monkeypatch.setattr(mcp, "ClientSession", FakeClientSession)
    monkeypatch.setattr(mcp_stdio, "stdio_client", lambda _server: FakeStdio())

    args = argparse.Namespace(
        tsv=tmp_path / "results.tsv",
        project="demo-project",
        base_url=None,
        transports={"mcp"},
    )
    asyncio.run(sync.run(args))

    assert captured["server"]["env"]["RUNTRACE_BASE_URL"] == "https://trace.example"
    assert captured["server"]["env"]["RUNTRACE_API_TOKEN"] == "rt_synthetic"
    assert captured["initialized"] is True
    assert captured["sync"] == ("demo-project", 3)
