from __future__ import annotations

from pathlib import Path

from mono import Mono
from mono.credentials import resolve_connection


PROJECT = "integration-test-registry"
PREFIX = "integration-sdk-cli"
base_url, token = resolve_connection()
client = Mono(base_url=base_url, api_token=token, strict=True)
artifact_path = Path(__file__).with_name("real_sdk_artifact.txt")

with client.run(
    PROJECT,
    f"{PREFIX}-sdk-owner",
    "The SDK can own one real API run and persist helper payloads.",
    "Synthetic QA against the authenticated isolated API.",
    tags=["qa", "sdk", "synthetic"],
    configuration={"owner": "sdk", "fixture": "MonoDemo"},
) as tracked:
    run_id = tracked.id
    tracked.log_metric("qa_score", 1.0, step=1)
    tracked.log_metric("sdk_helper_checks", 3.0, step=1)
    tracked.log_event("SDK owner recorded metric and helper evidence", event_type="qa")
    artifact = tracked.log_artifact(
        str(artifact_path),
        name="real_sdk_artifact.txt",
        metadata={"source": "synthetic-qa"},
        kind="result",
    )
    text_artifact = tracked.log_text("real_sdk_output.log", "synthetic SDK output\n", kind="log")
    config_artifact = tracked.log_config(
        {"qa_mode": "real-api", "artifact_helper": True, "config_helper": True},
        name="real_sdk_config.json",
    )
    if not artifact or not text_artifact or not config_artifact:
        raise RuntimeError("SDK artifact/config helper returned no artifact")
    tracked.finish(
        "success",
        "SDK owner and artifact/config helpers completed",
        "One SDK-owned run persisted metrics, events, artifacts, and parameters.",
    )

detail = client.request("GET", f"/api/v1/runs/{run_id}")
artifact_names = sorted(item["name"] for item in detail["artifacts"])
assert detail["lifecycle"] == "completed"
assert {"real_sdk_artifact.txt", "real_sdk_output.log", "real_sdk_config.json"}.issubset(artifact_names)
assert detail["parameters"]["qa_mode"] == "real-api"
assert detail["metrics"]["qa_score"]["latest"] == 1.0
print(f"sdk-owner-run-id={run_id}")
print(f"sdk-owner-lifecycle={detail['lifecycle']}")
print(f"sdk-owner-artifacts={','.join(artifact_names)}")
print(f"sdk-owner-config-parameter={detail['parameters']['qa_mode']}")
