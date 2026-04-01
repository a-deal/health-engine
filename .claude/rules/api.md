---
paths:
  - "engine/gateway/**"
  - "scripts/run_v1_api.py"
---

# API Rules

- The API runs as a native launchd service (com.kiso.v1api), NOT Docker. Port 18800. See hub/decisions/2026-03-27-docker-to-launchd.md.
- NEVER manually kill the API process or use `launchctl load/unload`. KeepAlive respawns the process before your new one can bind the port.
- To restart: `bash scripts/restart-api.sh` (on Mac Mini) or `./scripts/deploy-api.sh` (from laptop). These handle bootout, kill-with-retry, pyc cache clearing, and health check.
- To deploy code changes from laptop: `./scripts/deploy-api.sh --test-first` (runs tests, rsyncs code, restarts cleanly).
- The v1 API (engine/gateway/v1_api.py) serves iOS sync. The legacy /api/{tool_name} routes serve Milo's MCP tools. Both must be registered in run_v1_api.py.
- Always test locally before pushing. Deploy rule is a hard rule.
- Auth: admin token in gateway.yaml, per-user tokens in token_persons map. Three auth methods: `?token=X` query param, `token` in JSON body, `Authorization: Bearer X` header.
