#!/bin/sh
set -eu

if [ "$#" -gt 1 ]; then
  echo "Usage: $0 [VERSION]" >&2
  exit 2
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required. Install it from https://docs.astral.sh/uv/getting-started/installation/" >&2
  exit 1
fi

if [ "$#" -eq 1 ]; then
  requirement="runtrace-ai==$1"
else
  requirement="runtrace-ai"
fi

echo "Installing $requirement from PyPI..."
uv tool install --force "$requirement"

if command -v runtrace >/dev/null 2>&1; then
  runtrace --version
else
  bin_dir=$(uv tool dir --bin)
  if [ -x "$bin_dir/runtrace" ]; then
    "$bin_dir/runtrace" --version
    echo "Add $bin_dir to PATH to run 'runtrace' directly."
  else
    echo "RunTrace installed, but its executable could not be located." >&2
    exit 1
  fi
fi
