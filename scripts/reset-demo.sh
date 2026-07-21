#!/bin/sh
set -eu

compose() {
  if command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@"
  else
    docker compose "$@"
  fi
}

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repo_root"

if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  compose down -v
  export MONO_DEV=true
  compose up -d --build
else
  rm -f "$repo_root/data/mono.db"
  echo "Removed native data/mono.db. Restart the API with MONO_SEED_DEMO=true to reseed the demo."
fi
