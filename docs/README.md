# Deployment guide

The included Compose stack is the supported single-host deployment baseline. It runs PostgreSQL, the API, and the web app with persistent named volumes. Review this guide and `auth.md` before making the instance reachable outside localhost.

For product behavior, see the [complete feature catalog](features.md).

## Deployment modes

Normal mode is empty, persistent, and protected by browser passwords:

```bash
docker compose up -d --build
```

The release images can be deployed without a source build:

```bash
docker compose -f docker-compose.yml -f docker-compose.ghcr.yml up -d
```

This pulls `ghcr.io/vano04/mono` and `ghcr.io/vano04/mono-web`. Both default to the version in `MONO_VERSION` or `0.1.6` and are published for Linux AMD64.

Development mode is unauthenticated and seeds an empty database:

```bash
MONO_DEV=true docker compose up -d --build
```

Development mode is for a trusted workstation only. It is not a production authentication option.

Demo mode runs the same web app and seeded dataset with server-enforced viewer access:

```bash
MONO_DEMO=true docker compose up -d --build
```

Visitors are signed in automatically as demo viewers. The web app hides mutation controls, while the API rejects all state-changing requests with `403 Demo mode is read-only`. Read-only search, downloads, dashboards, and live seeded metrics continue to work. Keep `MONO_DEV=false`; put only the web service behind your public reverse proxy when possible.

## Production checklist

Before exposing Mono on a network:

1. Put the web service behind a TLS-terminating reverse proxy and use a stable hostname.
2. Set `MONO_CORS_ORIGINS` to the exact public origin.
3. Set `MONO_SECURE_SESSION_COOKIE=true` when HTTPS is enabled.
4. Replace the example PostgreSQL credentials in `docker-compose.yml` or supply an environment-specific Compose override and secret management.
5. Keep PostgreSQL and the API private to the host or internal network where possible. The checked-in Compose file publishes the API on port 8000 for local development and diagnostics.
6. Keep `MONO_DEV=false`, and use `MONO_DEMO=true` only for an intentionally public read-only demo. Keep both `MONO_DEMO=false` and `MONO_SEED_DEMO=false` for a normal deployment.
7. Arrange database and artifact-volume backups, then test restoration.
8. Create separate expiring agent tokens for each CLI or MCP host and store them in that host's secret manager.
9. Add resource limits, log collection, and monitoring appropriate to the host.

## Environment

Compose accepts these deployment values from the shell or a local `.env` file:

```env
MONO_DEV=false
MONO_DEMO=false
MONO_CORS_ORIGINS=https://mono.example.com
MONO_SECURE_SESSION_COOKIE=true
MONO_SESSION_TTL_HOURS=168
MONO_SETUP_LINK_TTL_HOURS=24
MONO_CLAIM_TIMEOUT_SECONDS=300
MONO_MAX_ARTIFACT_SIZE=10485760
```

Do not commit a populated `.env` file. Use unique passwords stored in a password manager.

## Persistence and backups

Compose uses three named volumes:

- `mono-postgres` for PostgreSQL data;
- `mono-artifacts` for uploaded run artifacts.
- `mono-models` for the optional, regenerable embedding-model cache.

`docker compose down` preserves both. `docker compose down -v` deletes them permanently.

Back up PostgreSQL with the database's standard logical or physical backup tooling and back up the artifact volume at a matching point in time. A usable restore needs both stores. Test the process against a separate Compose project before relying on it.

## Upgrades

Before upgrading:

1. read the incoming changes and migration files;
2. back up the database and artifacts;
3. build the new images;
4. let the API container run `alembic upgrade head` during startup;
5. verify `/health`, sign-in, project access, and a representative artifact download.

Do not run two application versions against the same database during a schema migration unless that release explicitly supports rolling upgrades.

## Demo reset

`./scripts/reset-demo.sh` destroys the current Compose volumes, rebuilds the stack with `MONO_DEV=true`, and inserts demo records into the empty database. It is intentionally destructive and should never be part of deployment automation.

## Verification

```bash
docker compose config
MONO_DEV=true docker compose config
MONO_DEMO=true docker compose config
curl --fail http://localhost:8000/health
```

For repository-level tests and builds, use the commands in the root `README.md`.
