def inline_spec(title="Loss by step"):
    return {
        "$schema": "https://runtrace.dev/schemas/rtvis/v1.json",
        "version": 1,
        "title": title,
        "description": "Portable loss history",
        "datasets": {
            "loss": {
                "source": "inline",
                "rows": [
                    {"step": 1, "loss": 3.4, "optimizer": "adam"},
                    {"step": 2, "loss": 3.2, "optimizer": "adam"},
                ],
            }
        },
        "view": {
            "type": "card",
            "title": "Loss history",
            "children": [
                {"type": "chart", "chart": "line", "dataset": "loss", "x": "step", "y": "loss", "series": "optimizer"}
            ],
        },
    }


def test_visualization_crud_dashboard_and_portable_round_trip(fresh_database):
    created = fresh_database.post(
        "/api/v1/projects/dense-optimizer/visualizations",
        json={"name": "Optimizer loss", "description": "Generated in Codex", "spec": inline_spec()},
    )
    assert created.status_code == 201, created.text
    item = created.json()
    assert item["spec_version"] == 1
    assert item["resolved_datasets"]["loss"][1]["loss"] == 3.2

    listed = fresh_database.get("/api/v1/projects/dense-optimizer/visualizations")
    assert [entry["id"] for entry in listed.json()] == [item["id"]]
    dashboard = fresh_database.get("/api/v1/projects/dense-optimizer/dashboard").json()
    assert dashboard["visualizations"][0]["name"] == "Optimizer loss"

    updated = fresh_database.patch(
        f"/api/v1/projects/dense-optimizer/visualizations/{item['id']}",
        json={"visible": False, "sort_order": 2},
    )
    assert updated.status_code == 200
    assert updated.json()["visible"] is False
    assert updated.json()["revision"] == 2

    exported = fresh_database.get(f"/api/v1/projects/dense-optimizer/visualizations/{item['id']}/export")
    assert exported.status_code == 200
    document = exported.json()
    assert document["format"] == "runtrace-visualization"
    imported = fresh_database.post(
        "/api/v1/projects/flash-attention-kernel/visualizations/import",
        json={"document": document, "name": "Imported optimizer loss"},
    )
    assert imported.status_code == 201, imported.text
    assert imported.json()["spec"] == item["spec"]

    deleted = fresh_database.delete(f"/api/v1/projects/dense-optimizer/visualizations/{item['id']}")
    assert deleted.status_code == 204
    assert fresh_database.get(f"/api/v1/projects/dense-optimizer/visualizations/{item['id']}").status_code == 404


def test_visualization_guide_preview_and_strict_validation(fresh_database):
    guide = fresh_database.get("/api/v1/projects/dense-optimizer/visualizations/guide")
    assert guide.status_code == 200
    assert "card" in guide.json()["supported_nodes"]
    assert "javascript" in guide.json()["supported_nodes"]
    assert guide.json()["dataset_sources"]["runtrace"]["queries"] == ["runs", "experiments"]

    preview = fresh_database.post("/api/v1/projects/dense-optimizer/visualizations/preview", json=inline_spec())
    assert preview.status_code == 200
    assert preview.json()["valid"] is True

    unsafe = inline_spec("Unsafe")
    unsafe["view"]["html"] = "<script>alert(1)</script>"
    rejected = fresh_database.post("/api/v1/projects/dense-optimizer/visualizations/preview", json=unsafe)
    assert rejected.status_code == 422

    widget = inline_spec("Interactive widget")
    widget["view"] = {
        "type": "javascript",
        "height": 280,
        "markup": '<div class="card"><button class="btn">Select</button><div id="value"></div></div>',
        "styles": "#value { color: var(--primary); }",
        "script": "document.querySelector('#value').textContent = window.runtrace.datasets.loss.length;",
    }
    accepted = fresh_database.post("/api/v1/projects/dense-optimizer/visualizations/preview", json=widget)
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["spec"]["view"]["script"] == widget["view"]["script"]

    widget["view"]["markup"] = "<script>alert(1)</script>"
    rejected = fresh_database.post("/api/v1/projects/dense-optimizer/visualizations/preview", json=widget)
    assert rejected.status_code == 422

    missing_dataset = inline_spec("Missing")
    missing_dataset["view"]["children"][0]["dataset"] = "unknown"
    rejected = fresh_database.post("/api/v1/projects/dense-optimizer/visualizations/preview", json=missing_dataset)
    assert rejected.status_code == 422


def test_runtrace_dataset_is_resolved_from_live_project_records(fresh_database):
    spec = {
        "version": 1,
        "title": "Kept runs",
        "datasets": {"runs": {"source": "runtrace", "query": "runs", "filters": {"lifecycle": "completed", "limit": 3}}},
        "view": {
            "type": "table",
            "dataset": "runs",
            "columns": [
                {"key": "display_id", "label": "Run", "format": "text"},
                {"key": "validation_loss", "label": "Loss", "format": "number"},
            ],
        },
    }
    created = fresh_database.post(
        "/api/v1/projects/dense-optimizer/visualizations",
        json={"name": "Live runs", "spec": spec},
    )
    assert created.status_code == 201, created.text
    rows = created.json()["resolved_datasets"]["runs"]
    assert len(rows) == 3
    assert all(row["lifecycle"] == "completed" for row in rows)
    assert all("validation_loss" in row for row in rows)
