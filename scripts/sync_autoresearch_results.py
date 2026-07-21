from __future__ import annotations

import argparse
import atexit
import asyncio
import csv
import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx

from mono.credentials import resolve_connection


TRANSPORTS = ("http", "python", "mcp")
IMPORT_FAILURE_SUMMARY = "Autoresearch import failed after run creation"


def read_rows(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    required = {"commit", "config", "val_loss", "train_time_s", "status", "description"}
    if not rows or set(rows[0]) != required:
        raise ValueError(f"expected TSV columns {sorted(required)}")
    for index, row in enumerate(rows, start=1):
        if row["status"] not in {"keep", "discard", "crash"}:
            raise ValueError(f"row {index} has unsupported status {row['status']!r}")
        row["source_row"] = index
        row["val_loss"] = float(row["val_loss"].replace(",", ""))
        row["train_time_s"] = float(row["train_time_s"].replace(",", ""))
    return rows


def transport_for(row: dict[str, Any]) -> str:
    transport = TRANSPORTS[(row["source_row"] - 1) % len(TRANSPORTS)]
    if row["status"] == "crash" and transport == "mcp":
        return "http"
    return transport


def create_payload(row: dict[str, Any], transport: str) -> dict[str, Any]:
    return {
        "name": row["config"],
        "hypothesis": row["description"],
        "change_summary": f"Autoresearch configuration {row['config']}",
        "metric_mode": "scalar",
        "git_commit": row["commit"],
        "configuration": {
            "config_path": row["config"],
            "autoresearch_status": row["status"],
            "source_file": "results.tsv",
            "source_row": row["source_row"],
            "sync_transport": transport,
        },
    }


def disposition(status: str) -> str:
    return {"keep": "kept", "discard": "discarded"}[status]


def summary(row: dict[str, Any]) -> str:
    return f"val_loss={row['val_loss']:g}; train_time_s={row['train_time_s']:g}"


def existing_source_rows(client: httpx.Client, project: str) -> set[int]:
    response = client.get(f"/api/v1/projects/{project}/runs?include_archived=true")
    response.raise_for_status()
    completed: set[int] = set()
    for run in response.json():
        configuration = run.get("configuration", {})
        if configuration.get("source_file") != "results.tsv" or configuration.get("source_row") is None:
            continue
        source_row = int(configuration["source_row"])
        lifecycle = run.get("lifecycle")
        source_status = configuration.get("autoresearch_status")
        if lifecycle == "completed" and source_status in {None, "keep", "discard"}:
            completed.add(source_row)
            continue
        if lifecycle == "crashed":
            result_summary = run.get("result_summary")
            expected_summary = run.get("hypothesis") or (
                "Run aborted" if configuration.get("sync_transport") == "python" else ""
            )
            expected_source_crash = source_status == "crash" and result_summary == expected_summary
            legacy_source_crash = source_status is None and result_summary != IMPORT_FAILURE_SUMMARY
            if expected_source_crash or legacy_source_crash:
                completed.add(source_row)
            continue
        recovery = client.post(
            f"/api/v1/runs/{run['id']}/crash",
            json={"error_summary": IMPORT_FAILURE_SUMMARY},
        )
        recovery.raise_for_status()
    return completed


def sync_http(client: httpx.Client, project: str, row: dict[str, Any]) -> str:
    created = client.post(
        f"/api/v1/projects/{project}/runs", json=create_payload(row, "http")
    )
    created.raise_for_status()
    run_id = created.json()["id"]
    try:
        metrics = client.post(
            f"/api/v1/runs/{run_id}/metrics",
            json={"metrics": [
                {"name": "validation_loss", "value": row["val_loss"]},
                {"name": "train_time_s", "value": row["train_time_s"]},
            ]},
        )
        metrics.raise_for_status()
        if row["status"] == "crash":
            completed = client.post(
                f"/api/v1/runs/{run_id}/crash", json={"error_summary": row["description"]}
            )
        else:
            completed = client.post(
                f"/api/v1/runs/{run_id}/finish",
                json={
                    "disposition": disposition(row["status"]),
                    "result_summary": summary(row),
                    "conclusion": row["description"],
                },
            )
        completed.raise_for_status()
    except Exception:
        try:
            recovery = client.post(
                f"/api/v1/runs/{run_id}/crash",
                json={"error_summary": IMPORT_FAILURE_SUMMARY},
            )
            recovery.raise_for_status()
        except Exception:
            pass
        raise
    return run_id


def sync_python(base_url: str, api_token: str | None, project: str, row: dict[str, Any]) -> str:
    from mono import Mono

    client = Mono(base_url=base_url, api_token=api_token, strict=True, timeout=30)
    payload = create_payload(row, "python")
    try:
        with client.run(
            project,
            payload.pop("name"),
            payload.pop("hypothesis"),
            working_directory=os.getcwd(),
            **payload,
        ) as run:
            run.log_metrics({"validation_loss": row["val_loss"], "train_time_s": row["train_time_s"]})
            if row["status"] == "crash":
                run.abort(row["description"])
            else:
                run.finish(disposition(row["status"]), summary(row), row["description"])
            assert run.id
            return run.id
    finally:
        atexit.unregister(client._flush_at_exit)
        client.client.close()


def mcp_value(result: Any) -> dict[str, Any]:
    if getattr(result, "isError", False):
        raise RuntimeError(str(result.content))
    if getattr(result, "structuredContent", None):
        value = result.structuredContent
        return value.get("result", value)
    return json.loads(result.content[0].text)


async def sync_mcp(session: Any, project: str, row: dict[str, Any]) -> str:
    payload = create_payload(row, "mcp")
    created = mcp_value(await session.call_tool("create_run", {
        "project": project,
        "name": payload["name"],
        "hypothesis": payload["hypothesis"],
        "change_summary": payload["change_summary"],
        "git_commit": row["commit"],
        "metric_mode": payload["metric_mode"],
        "configuration": payload["configuration"],
    }))
    run_id = created["id"]
    try:
        for name, row_key in (("validation_loss", "val_loss"), ("train_time_s", "train_time_s")):
            mcp_value(await session.call_tool("log_metric", {
                "run_id": run_id, "name": name, "value": row[row_key]
            }))
        mcp_value(await session.call_tool("finish_run", {
            "run_id": run_id,
            "disposition": disposition(row["status"]),
            "result_summary": summary(row),
            "conclusion": row["description"],
        }))
    except Exception:
        try:
            mcp_value(await session.call_tool("crash_run", {
                "run_id": run_id,
                "error_summary": IMPORT_FAILURE_SUMMARY,
            }))
        except Exception:
            pass
        raise
    return run_id


async def run(args: argparse.Namespace) -> None:
    rows = read_rows(args.tsv)
    counts = {name: 0 for name in TRANSPORTS}
    skipped = 0
    base_url, api_token = resolve_connection(args.base_url)
    headers = {"Authorization": f"Bearer {api_token}"} if api_token else {}
    with httpx.Client(base_url=base_url, headers=headers, timeout=30) as http:
        known = existing_source_rows(http, args.project)
        selected = [row for row in rows if transport_for(row) in args.transports]
        skipped = sum(row["source_row"] in known for row in selected)

        mcp_rows = [row for row in selected if transport_for(row) == "mcp" and row["source_row"] not in known]
        non_mcp_rows = [
            row for row in selected
            if transport_for(row) != "mcp" and row["source_row"] not in known
        ]
        for row in non_mcp_rows:
            transport = transport_for(row)
            if transport == "http":
                sync_http(http, args.project, row)
            else:
                sync_python(base_url, api_token, args.project, row)
            counts[transport] += 1

    if mcp_rows:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        server_env = {**os.environ, "MONO_BASE_URL": base_url}
        if api_token:
            server_env["MONO_API_TOKEN"] = api_token
        server = StdioServerParameters(
            command=sys.executable,
            args=["-m", "mono_mcp.server"],
            env=server_env,
        )
        async with stdio_client(server) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                for row in mcp_rows:
                    await sync_mcp(session, args.project, row)
                    counts["mcp"] += 1

    print(json.dumps({"synced": counts, "skipped_existing": skipped, "total_rows": len(rows)}))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("tsv", type=Path)
    parser.add_argument("--project", default="optimizer")
    parser.add_argument("--base-url")
    parser.add_argument("--transport", dest="transports", action="append", choices=TRANSPORTS)
    args = parser.parse_args()
    args.transports = set(args.transports or TRANSPORTS)
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
