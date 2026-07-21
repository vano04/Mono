# Mono CLI/SDK integration fixture

This synthetic project is only a local protocol fixture for QA. It accepts the
small subset of Mono API calls needed to exercise the installed CLI and
Python SDK, records runs in memory, and never records authorization headers.

The fixture is intentionally separate from the Mono source tree's runtime
services. The test scripts use `uv run` for every Python invocation.
