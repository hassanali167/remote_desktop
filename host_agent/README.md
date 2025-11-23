# Host Agent (Phase 2 Stub)

This directory contains the Phase 2 scaffold for the privileged host agent.
It currently exposes HTTP endpoints that mimic the future gRPC API so the
Flask gateway and browser client can be developed in parallel.

## Features (Stub)
- Token-protected HTTP API (`Authorization: Bearer <token>`).
- `/api/input`, `/api/wake`, `/api/keepalive`, `/api/health`, `/api/webrtc/offer`.
- Optional mock MJPEG stream for local testing.

## Install
```bash
cd host_agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m host_agent
```

## Environment
| Variable | Default | Description |
|----------|---------|-------------|
| `HOST_AGENT_BIND` | `127.0.0.1` | Listen address |
| `HOST_AGENT_PORT` | `8787` | Listen port |
| `HOST_AGENT_TOKEN` | `replace-this-agent-token` | Shared secret |
| `HOST_AGENT_LOG_LEVEL` | `INFO` | Logging level |
| `HOST_AGENT_STUB_CAPTURE` | `true` | Enables `/api/stream/mock` |

## Next Steps
- Replace FastAPI HTTP stub with hardened gRPC server.
- Wire into PipeWire/X11 capture and `/dev/uinput` injection.
- Package as systemd service.

