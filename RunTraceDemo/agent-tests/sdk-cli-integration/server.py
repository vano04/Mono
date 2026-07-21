from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Lock
from urllib.parse import urlsplit


TOKEN = "synthetic-qa-token"
PROJECT_ID = "project-synthetic-qa"

state = {
    "runs": {},
    "next_run": 1,
    "context_requests": 0,
    "search_requests": 0,
    "auth_requests": 0,
}
lock = Lock()


def json_bytes(payload: object) -> bytes:
    return json.dumps(payload, sort_keys=True).encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    # Keep the single-threaded fixture from waiting on an idle keep-alive
    # connection between sequential CLI/SDK requests.
    protocol_version = "HTTP/1.0"

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def send_json(self, status: int, payload: object) -> None:
        body = json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if not length:
            return {}
        return json.loads(self.rfile.read(length))

    def authorized(self) -> bool:
        return self.headers.get("Authorization") == f"Bearer {TOKEN}"

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/api/v1/auth/status":
            with lock:
                state["auth_requests"] += 1
            self.send_json(200, {"authenticated": self.authorized()})
            return
        if path == "/__state":
            with lock:
                runs = list(state["runs"].values())
                payload = {
                    "auth_requests": state["auth_requests"],
                    "context_requests": state["context_requests"],
                    "search_requests": state["search_requests"],
                    "runs": runs,
                }
            self.send_json(200, payload)
            return
        if not self.authorized():
            self.send_json(401, {"detail": "unauthorized"})
            return
        if path == "/api/v1/projects/qa-project/context":
            with lock:
                state["context_requests"] += 1
            self.send_json(
                200,
                {
                    "project": {"id": PROJECT_ID, "slug": "qa-project", "name": "Synthetic QA"},
                    "program": "Exercise CLI and SDK lifecycle paths",
                    "exclusions": ["No production data"],
                    "metric": {"name": "synthetic_loss", "direction": "minimize"},
                    "baseline": None,
                    "claimable_experiments": [],
                },
            )
            return
        if path == "/api/v1/projects/qa-project":
            self.send_json(200, {"id": PROJECT_ID, "slug": "qa-project", "name": "Synthetic QA"})
            return
        if path.startswith("/api/v1/runs/"):
            run_id = path.rsplit("/", 1)[-1]
            with lock:
                run = state["runs"].get(run_id)
            if run is None:
                self.send_json(404, {"detail": "run not found"})
            else:
                self.send_json(200, run)
            return
        self.send_json(404, {"detail": "not found"})

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        if path == "/__shutdown":
            self.send_json(200, {"ok": True})
            self.server.shutdown()
            return
        if not self.authorized():
            self.send_json(401, {"detail": "unauthorized"})
            return
        payload = self.read_json()
        if path == "/api/v1/search":
            with lock:
                state["search_requests"] += 1
            self.send_json(
                200,
                {
                    "project": payload.get("project"),
                    "query": payload.get("query"),
                    "count": 1,
                    "results": [{"id": "synthetic-evidence-1", "display_id": "EXP-QA-001", "name": "CLI/SDK smoke evidence"}],
                },
            )
            return
        if path == "/api/v1/projects/qa-project/runs":
            with lock:
                number = state["next_run"]
                state["next_run"] += 1
                run_id = f"run_synthetic_{number:03d}"
                run = {
                    "id": run_id,
                    "display_id": f"RUN-QA-{number:03d}",
                    "project_id": PROJECT_ID,
                    "project": "qa-project",
                    "name": payload.get("name", ""),
                    "hypothesis": payload.get("hypothesis", ""),
                    "lifecycle": "running",
                    "disposition": None,
                    "result_summary": "",
                    "conclusion": "",
                    "error_summary": "",
                    "metrics": [],
                    "events": [],
                }
                state["runs"][run_id] = run
            self.send_json(201, run)
            return
        parts = path.split("/")
        if len(parts) == 6 and parts[:4] == ["", "api", "v1", "runs"]:
            run_id, action = parts[4], parts[5]
            with lock:
                run = state["runs"].get(run_id)
                if run is None:
                    self.send_json(404, {"detail": "run not found"})
                    return
                if action == "metrics":
                    run["metrics"].extend(payload.get("metrics", []))
                elif action == "events":
                    run["events"].append(payload)
                elif action == "finish":
                    run["lifecycle"] = "completed"
                    run["disposition"] = payload.get("disposition")
                    run["result_summary"] = payload.get("result_summary", "")
                    run["conclusion"] = payload.get("conclusion", "")
                elif action == "crash":
                    run["lifecycle"] = "crashed"
                    run["disposition"] = "discarded"
                    run["error_summary"] = payload.get("error_summary", "")
                else:
                    self.send_json(404, {"detail": "unknown run action"})
                    return
                snapshot = dict(run)
            self.send_json(200, snapshot)
            return
        self.send_json(404, {"detail": "not found"})


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    server = HTTPServer(("127.0.0.1", port), Handler)
    print(f"fixture-listening={port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
