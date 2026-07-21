#!/bin/sh
set -eu

compose() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
  elif command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@"
  else
    echo "Docker Compose is required." >&2
    exit 1
  fi
}

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repo_root"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required. Install Docker Desktop or Docker Engine with Compose support." >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "The Docker daemon is not running." >&2
  exit 1
fi

echo "Building and starting Mono..."
compose up -d --build --wait

echo "Mono is ready."
compose ps
echo "Web: http://localhost:3000"
echo "API: http://localhost:8000"
