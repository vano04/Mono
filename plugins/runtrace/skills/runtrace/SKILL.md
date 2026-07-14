---
name: runtrace
description: Use when planning or running research experiments, checking what has already been tried, coordinating agent claims, logging metrics or outcomes, or preserving conclusions for later agents through a connected RunTrace instance.
---

# RunTrace

Use RunTrace to make experimental work evidence-driven and recoverable across agent sessions.

## Workflow

1. Before proposing a change, call `get_project_context` and search for related experiments. Summarize the evidence that affects the plan.
2. If working from the shared queue, claim an experiment before editing. Do not claim work that another worker already owns.
3. Create a run when execution begins. Include the hypothesis, reasoning, relevant configuration, and references to evidence used.
4. Log primary and diagnostic metrics with stable names. Log meaningful checkpoints and failures as events.
5. Finish every started run. Record the disposition, concise result summary, and a reusable conclusion. A failed result is useful evidence and must not be hidden.

## Custom visualizations

When the user asks to generate, save, import, or revise a project visualization:

1. Call `get_visualization_guide` for the target project before authoring JSON. The returned schema is authoritative for that RunTrace version.
2. Prefer shadcn-backed layout, card, table, badge, and metric nodes. Use chart nodes for marks that shadcn does not directly provide; RunTrace applies its semantic theme automatically.
3. Put user-supplied tabular data in an `inline` dataset. Use a `runtrace` dataset with a supported query when the widget should stay live as project records change.
4. Call `preview_visualization` when the specification is complex or generated from ambiguous data. Fix validation errors before saving.
5. Call `generate_visualization` to save the validated specification. Prefer the trusted ShadCN-backed nodes. When they cannot express the requested interaction, use a `javascript` node with separate `markup`, `styles`, and `script` fields; it runs in an isolated, network-disabled iframe and receives `window.runtrace.datasets` and `window.runtrace.theme`. Never include remote URLs or credentials.
6. Use `export_visualization` and `import_visualization` for portable project-to-project transfer. Preserve the versioned document wrapper instead of copying only the inner spec.

## Guardrails

- Never invent project slugs, run IDs, metrics, or results. Retrieve them or ask the user.
- Treat RunTrace writes as shared external state. Confirm intent before deleting tags or making unrelated mutations.
- Do not place API tokens, credentials, or private data in hypotheses, events, parameters, artifacts, or conclusions.
- Prefer search and context retrieval before proposing duplicate experiments.
- When the server is unavailable, report the connection failure clearly; do not claim that a run was recorded.

For connection setup and supported environment variables, read [references/connection.md](references/connection.md).
