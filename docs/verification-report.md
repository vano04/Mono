# Feature verification report

Date: 2026-07-21
Repository baseline: `680ddfc` (`master`)
Scope: current RunTrace source, normal and development Compose modes, PostgreSQL/pgvector, web application, HTTP/SSE, SDK, CLI, MCP, RTVis, importer, integrations, packaging, and release operations.

The canonical source-derived inventory is [features.md](features.md). This report records runtime evidence, defects fixed, and the few boundaries that still require an external release or impractical wall-clock waits.

## Outcome

- The complete Python suite passes: **119 passed, 0 failed**.
- The web permission suite passes: **3 passed, 0 failed**; ESLint, explicit TypeScript checking, Turbopack, and webpack production builds also pass.
- Wheel and source distribution builds pass, as do source, GHCR-overlay, and development Compose validation.
- A fresh authenticated PostgreSQL 17 + pgvector stack passed owner bootstrap, token and project setup, the complete live API matrix, real semantic retrieval, concurrency/locking probes, SSE through the production Next.js proxy, SDK/CLI/MCP/RTVis workflows, and authenticated browser QA.
- A separate disposable development stack passed authentication bypass, demo seeding, metric rotation, claim keepalive, and live browser streaming.
- All disposable projects/tokens were removed, all synthetic runs were terminal before cleanup, and the disposable development stack plus volumes were destroyed.

## Automated and build checks

| Check | Result | Evidence |
| --- | --- | --- |
| `uv run --extra dev --extra server --extra mcp pytest -q` | Pass | 119 passed. |
| `npm --prefix apps/web test` | Pass | 3 project-role capability regressions. |
| `npm --prefix apps/web run lint` | Pass | ESLint exited 0. |
| `npm --prefix apps/web run typecheck` | Pass | TypeScript exited 0. |
| `npm --prefix apps/web run build` | Pass | Next.js 16.2.10 Turbopack production build passed in the source image; the dynamic SSE route was emitted. |
| `npm --prefix apps/web run build -- --webpack` | Pass | Independent webpack production build passed. |
| `uv build` | Pass | `runtrace_ai-0.1.3.tar.gz` and wheel produced. |
| Source API/web image build and health checks | Pass | Both images rebuilt; PostgreSQL, API, and web services became healthy. |
| Source, GHCR-overlay, and `RUNTRACE_DEV=true` Compose configuration | Pass | All configurations render successfully. |
| Workflow YAML and shell syntax | Pass | CI/release workflows parse; install/update/reset scripts pass syntax checks. |
| `git diff --check` | Pass | No whitespace errors. |

`npm audit --omit=dev` reports two moderate entries for one nested advisory: Next.js 16.2.10 pins PostCSS 8.4.31, affected by `GHSA-qx2v-qp2m-jg93` (`CVE-2026-41305`, fixed in PostCSS 8.5.10). The current stable Next.js line has no supported audit fix; npm proposes an unrelated breaking downgrade. RunTrace does not stringify user-supplied CSS, so the known exploit path is not exposed, and no unsupported dependency override was added.

## Live PostgreSQL and HTTP verification

The disposable normal-mode stack used fresh named PostgreSQL, artifact, and model volumes on the production ports. Owner password login and a project-scoped bearer token authenticated the checks.

The reusable harness at `RunTraceDemo/live-e2e/api_matrix.py` passed 13 grouped scenarios:

1. health, proxied Swagger, and proxied OpenAPI;
2. bearer identity and project-grant restrictions;
3. project context, versioned program, exclusions, and metric settings;
4. proposal claim, worker ownership, release/start, and terminal lifecycle;
5. metric/event idempotency plus parameter upserts;
6. artifact upload/download, 500 KB preview truncation, 10 MB rejection, and binary-preview rejection;
7. RTVis source/inline datasets, preview/create/update/export/import/delete, row/document/depth limits, and run-source protection;
8. reverse-proxy SSE initial frames, resume cursors, and terminal replay;
9. baseline, progress, keyword search, archive/restore, and dashboard aggregates;
10. crash idempotency and terminal replay;
11. custom result-type lifecycle;
12. memberships and tag CRUD/filter behavior;
13. login throttling.

Additional live probes passed:

- The optional FastEmbed model indexed PostgreSQL vectors and returned a semantic-only result for a query with no keyword overlap (`semantic_score=0.7275`).
- Alembic reached `0014_search_embedding_hnsw`; repeated upgrade was a no-op and `alembic check` found no pending operations.
- The partial HNSW index was valid/ready with `vector_cosine_ops`, and PostgreSQL selected it for a forced 384-dimensional cosine query.
- Twelve simultaneous proposals and twelve simultaneous runs received unique per-project display IDs.
- Two simultaneous claims produced one `200` winner and one `409`; two simultaneous starts produced one `201` winner and one `409`.
- Concurrent finish/crash replays converged on one terminal value, a reused request ID remained scoped to its run, baseline deletion cleared its reference, and a visualization source blocked run deletion until the widget was removed.
- With a one-second configured claim timeout, a real abandoned pending claim returned to `proposed` after 2.1 seconds.
- The autoresearch TSV importer created four rows across HTTP, Python, MCP, and intended source-crash behavior; an immediate second import skipped all four, then removed its disposable project and token.

## Browser QA

All browser interaction used the Codex in-app browser against production-built containers. No cookies, storage, token secrets, or password hashes were inspected.

### Authentication, identities, and account controls

- Fresh owner bootstrap, onboarding, project creation, sign-in, invalid-login feedback, and sign-out passed.
- A synthetic member consumed a one-time setup link, set a password, and signed in independently.
- Before membership, the member saw no projects and direct project access returned the access-denied state.
- Identity search, role/status filters, Member↔Admin, Suspend↔Reactivate, project Viewer↔Editor membership, setup-link refresh, token creation/scoping/one-time secret display, and token listing passed.
- Light, dark, and system theme controls, compact rows, appearance reset, English↔Spanish locale persistence, and password rotation with restoration passed.
- The synthetic membership was removed and the synthetic identity was suspended after verification.

### Project and evidence workflows

- Dashboard counts, baseline, recorded-worker count, best-so-far chart, time/metric controls, and include/exclude tag filters rendered and updated.
- A browser proposal was created, inspected, archived, restored, found through search, and deleted.
- Empty-query browsing, keyword query, newest/metric sorting, archive, and record detail dialogs passed.
- A real SDK run displayed its baseline curve, metrics, parameters/configuration, conclusion, structured event, and three artifact kinds; supported previews and downloads worked.
- Goal/repository/program/exclusions/metric settings loaded; a goal edit was saved and reverted. Tag create/rename/delete and project Viewer↔Editor membership passed.
- Built-in result displays and a custom type were exercised through API/MCP. Project widgets passed preview, create, edit, visibility, export/import, and delete.
- A temporary JavaScript widget updated inside its iframe. The iframe had exactly `sandbox="allow-scripts"`, and its CSP included `connect-src 'none'`.

### Read-only viewer regression

The browser found that the API correctly rejected viewer mutations but the web UI still exposed proposal, record-action, artifact-upload, and Settings controls. The fix adds the effective `access_role` to the dashboard and derives explicit viewer/editor/owner capabilities in the web app.

Post-fix browser proof:

- viewers retain dashboards, progress, search, archive, record details, previews/downloads, and visualizations;
- proposal buttons, record actions, baseline/archive/delete/edit actions, artifact upload, and Settings navigation are absent;
- direct viewer access to `/settings` shows a read-only explanation;
- editors retain project-data/settings mutations; only owners/admins receive membership and project-delete controls;
- owner proposal/action/Settings controls remained present.

### Docs, responsive UI, and live streaming

- `/docs` rendered the quick start, SDK, CLI, MCP, integration, HTTP/SSE, and lifecycle guidance.
- `/api/docs` rendered Swagger 0.1.3 through the web proxy, and `/openapi.json` loaded.
- Desktop and mobile dashboard renders passed without visible clipping. Captures: [desktop (739×846)](../RunTraceDemo/browser-e2e/dashboard-desktop.png) and [mobile (375×812)](../RunTraceDemo/browser-e2e/dashboard-mobile.png).
- Final browser console checks returned no warnings or errors.
- A live seeded run moved from 11 metric points at step 1000 to a reset stream and then two points through step 100; the open detail dialog updated through SSE without reload.

## Development-mode verification

A second Compose project used isolated ports 3100/8100 and disposable volumes. It passed:

- visible `Dev · no auth` browser state and authenticated dev principal;
- the three seeded projects, one active run, four proposals, current baseline, and six recorded workers;
- the ten-second metric loop (`400 → 500` in the harness observation);
- pending-claim keepalive advancement with a 30-second timeout;
- seeded dashboard, queue, history, progress chart, and live run detail in the browser.

The exact `runtrace-dev-qa` containers, network, and three named volumes were removed after the check.

## Luna xhigh Codex agentic tests

Only Codex was used for agentic feature testing. Four separate Luna xhigh tasks used files under `RunTraceDemo/agent-tests`:

| Scope | Task | Result |
| --- | --- | --- |
| Context/search/tags | `019f8392-d128-7003-9f7e-668c706e6269` | Authenticated context, search, tag CRUD, and cleanup passed. |
| Claim/run lifecycle | `019f8392-cede-7cd3-9dc4-eb94f795db54` | Claim/release behavior passed. The installed MCP schema lacked current `worker_id`, so the agent safely released `EXP-024`; current source exposes and tests the field. |
| SDK/CLI | `019f8392-d39e-73b1-ab24-9cf706c121b6` | SDK-owned and attached runs, metrics, events, parameters, artifacts, CLI success, and CLI failure passed. |
| RTVis | `019f8392-d65b-7f20-8f9d-898169b305e6` | Guides, preview/generate/get/list/update, revision, export/import, custom result type, and cleanup passed. Invalid preview errors remain terse through the MCP client but are correctly rejected. |

The published `runtrace-ai==0.1.3` CLI reproduced an older double-terminal failure path: a child exit 23 became a traceback/exit 1. Current source returns the exact child exit 23, records one crash, suppresses a second context-exit abort, and has a regression test. A refreshed distribution is required for installed users to receive that fix and the current MCP `worker_id` schema.

## Defects fixed

| Defect | Fix and proof |
| --- | --- |
| Terminal runs could be rewritten by late crash/finish calls, and request IDs leaked across runs. | Lock terminal mutation, scope audit replay to subject/run, persist event replay IDs, and reject non-replay terminal rewrites. Unit and live concurrent replay checks pass. |
| Running/source/baseline run deletion could strand references or race other transitions. | Lock project→run/source records consistently, reject running/source deletion, and clear a deleted baseline. Live PostgreSQL deletion/reference checks pass. |
| Concurrent display IDs, claims, and starts could race. | PostgreSQL row locks now serialize allocation and lifecycle transitions. Live 12+12 allocation and two-way claim/start races pass. |
| Strict SDK writes buffered HTTP rejections; a full buffer evicted evidence; terminal writes could overtake evidence; manual abort could repeat. | Separate status/transport failures, fail on capacity, preserve evidence-before-terminal order, retain strict flush failures, and track terminal ownership. SDK regressions pass. |
| `runtrace exec` could turn the child's nonzero status into a second abort traceback. | Treat the explicit crash as terminal before context exit. Current source returns the exact child status in a live repro. |
| Scoped bearer tokens could escape project grants or perform browser/credential administration. | Enforce immutable grants and require browser sessions for tokens, identities, password, preferences, and onboarding. Auth/API/browser checks pass. |
| Development token creation and repeated owner recovery failed unclearly. | Return a clean dev-mode conflict; owner recovery reactivates and revokes sessions on every configured start. Auth regressions pass. |
| Claimed experiments could start without the recorded worker identifier. | Add/validate `worker_id` through API, schema, MCP, docs, and tests. Live ownership races pass. |
| Importer credentials, canonical fields, crash recovery, status validation, and idempotency were inconsistent. | Resolve one connection for all transports, validate before dispatch, recover incomplete rows, and preserve canonical fields. Unit and live four-row replay checks pass. |
| RTVis source-bound widgets lost source context and were not portable. | Lock/prevalidate source runs, resolve previews/updates, protect deletion, and freeze bound rows during export. API/MCP/browser checks pass. |
| Swagger requested an unproxied root `/openapi.json`. | Add the root proxy mapping; Swagger and OpenAPI now render through the production web service. |
| Cross-project shorthand could crash SSE lookup. | Resolve canonical IDs first and return the normal ambiguity conflict. Regression passes. |
| The production Next proxy buffered small SSE frames behind compression. | Give the stream a dedicated route handler, make broad API rewrites fallback-only, and forward a no-transform streaming body. Direct and proxied initial/resume/terminal probes pass. |
| Fresh PostgreSQL installs skipped the HNSW index because the table already existed before migration 0003. | Add idempotent PostgreSQL migration 0014 and matching metadata. Fresh upgrade, repeat upgrade, Alembic diff, index validity, and planner use pass. |
| Viewer mutation controls remained visible despite API 403 enforcement. | Add role-aware viewer/editor/owner capabilities throughout navigation, records, uploads, and Settings. Web tests and authenticated browser regression pass. |
| Release-created version tags did not publish containers because `GITHUB_TOKEN` events do not recursively trigger workflows. | Publish on direct `v*` tag pushes, retain validated exact-tag manual dispatch, and derive the OCI version from the tag. Workflow parsing/contract checks pass. |
| `reset-demo.sh` deleted a relative database path from the caller's directory. | Resolve and enter repository root, then use an absolute repository data path. Syntax and off-root resolution checks pass. |
| UI/docs overstated connected workers and public audit history. | Use “Recorded workers” and document internal-only audit rows and the lack of dispatch/heartbeat/audit-history UI. |

## Distribution and remaining boundaries

- Public GHCR `0.1.2` and `0.1.3` API/web tags were absent during verification; `latest` still identified 0.1.1 at revision `4134d97…`. Disposable default-entrypoint health smokes for the available 0.1.1 runtime and web images passed.
- The workflow repair is local, uncommitted source. The configured `vano04` GitHub credential is valid with repository, workflow, and package-write access, but manual 0.1.3 backfill was not dispatched because publishing packages is external release state. Review and commit the workflow change, then dispatch the exact release tag or publish a new version containing these fixes.
- The installed PyPI/plugin artifacts predate current source fixes as described above; they need a versioned distribution/plugin refresh.
- One-time setup-link expiry and 1–365-day token expiry have automated coverage but were not observed for hours/days in real time.
- English and Spanish were exercised live; all 11 locale catalogs build and type-check, but no manual visual sweep was performed for every translated string.
- Install/update/reset scripts were parsed and their critical path/root logic was validated. They were not run against the user's persistent original deployment because source image rebuilds, repeated container recreation with preserved data, and exact disposable-volume teardown supplied the relevant runtime evidence without risking that deployment.
- Public PyPI/GHCR release publication was intentionally not performed. No other local permission-limited feature remains.
