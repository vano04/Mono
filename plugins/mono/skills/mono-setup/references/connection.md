# Connection setup

The plugin starts `mono-mcp` through `uvx`; the host needs `uv` and first-launch package access.

Save a normal agent token without exposing it in shell history:

```bash
mono auth - --base-url "https://mono.example.com"
```

MCP rereads the user-only credential file on each request. `MONO_BASE_URL` and `MONO_API_TOKEN` override it. Never commit or log tokens.

For a trusted local no-auth stack, use:

```bash
mono auth rt_mono_dev --base-url http://localhost:8000
```

Keep development mode local. Call `list_projects` afterward to verify access and retrieve canonical slugs.
