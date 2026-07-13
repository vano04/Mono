# RunTrace

RunTrace v0.1 is a self-hosted experiment registry and persistent memory layer for autonomous research agents. It keeps hypotheses, prior evidence, code metadata, live metrics, outcomes, and conclusions together so each new run can build on what was already learned.

The application starts empty. Create the first project in the web app or through the API; no sample project or experiment data is inserted by the default configuration.

## Stack

- Next.js 16, TypeScript, Tailwind CSS, and shadcn/ui
- FastAPI, SQLAlchemy 2, and Pydantic
- PostgreSQL 17 with pgvector
- `BAAI/bge-small-en-v1.5` embeddings through FastEmbed
- Server-Sent Events for live run metrics, events, and status
- Python SDK, CLI, and Python MCP SDK server
- Docker Compose for the complete deployment

## Included workflows

- create and search project-scoped registries
- edit versioned `program.md` and research exclusions
- propose and atomically claim experiments
- create, stream, complete, crash, archive, restore, and soft-delete runs
- record metrics, parameters, events, source metadata, and downloadable artifacts
- set an auditable completed-run baseline
- render strict best-so-far progress for an exact emitted metric name
- hybrid semantic and keyword evidence retrieval, backed by pgvector
- retrieve the complete agent bootstrap context through HTTP, CLI, SDK, or MCP

## Run the full stack

```bash
docker compose up --build
```

Open:

- Web app: `http://localhost:3000`
- API health: `http://localhost:8000/health`
- Interactive API reference: `http://localhost:8000/docs`

The embedding model is downloaded into the `runtrace-models` Docker volume when semantic indexing is first needed. Keyword retrieval remains available if the model cannot be loaded.

To clear all database, artifact, and model volumes:

```bash
docker compose down -v
```

## Native development

Native API development expects PostgreSQL with the `vector` extension. Copy `.env.example`, adjust the database URL, then run:

```bash
UV_CACHE_DIR=.uv-cache uv sync --extra dev
UV_CACHE_DIR=.uv-cache uv run uvicorn runtrace_api.main:app --reload --port 8000
```

In a second terminal:

```bash
cd apps/web
npm install
npm run dev
```

The Next.js server proxies `/api/*` to `INTERNAL_API_URL`, which defaults to `http://localhost:8000`.

## Agent closed loop

```bash
runtrace context <project-slug>
runtrace search <project-slug> "what has already been tried?"
runtrace exec --project <project-slug> --name "new variation" \
  --hypothesis "this should improve the primary metric" -- \
  python benchmark.py
```

Run the MCP server over stdio:

```bash
RUNTRACE_BASE_URL=http://localhost:8000 runtrace-mcp
```

## Verification

```bash
UV_CACHE_DIR=.uv-cache uv run pytest
npm --prefix apps/web run lint
npm --prefix apps/web run build
docker compose config
```

The historical `prototype/` directory is retained only as the accepted design source. Docker and development commands use the production Next.js app in `apps/web/`.
