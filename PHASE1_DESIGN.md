# Browser-Based Remote Desktop: Phase 1 Architecture

## Goals
- Control host even when session is locked/off-screen (AnyDesk/RustDesk parity)
- Perfect mouse & keyboard fidelity across browsers
- Browser-only client; no native apps
- Secure, LAN-first deployment (can extend to WAN later)

## High-Level Components
1. **Host Agent (system service)**
   - Runs as root via systemd
   - Captures desktop (Wayland + X11)
   - Injects input through privileged APIs (`/dev/uinput`, `libei`)
   - Provides wake/keep-alive
   - gRPC/Unix-socket API

2. **Web Gateway (Flask)**
   - Auth/session handling (existing)
   - Talks to Host Agent for video stream + input
   - Acts as WebRTC signaling server for browsers

3. **Browser Client**
   - WebRTC for video/audio
   - Pointer-lock + scancode keyboard
   - Dark UI (existing templates extended)

## Host Agent Architecture

### Processes
- `remote-agent.service` (Rust or Go)
  - Pipelines:
    - Capture: PipeWire (Wayland) / X11 fallback
    - Input: `/dev/uinput` + `libei` for Wayland-friendly injection
    - Power: DPMS, loginctl, inhibit API
  - IPC: gRPC over Unix domain socket (mutual auth tokens)

### gRPC Interface Sketch
```
service HostAgent {
  rpc StartStream(StreamRequest) returns (StreamMetadata);
  rpc StopStream(StreamId) returns (Ack);
  rpc InputEvent(InputMessage) returns (Ack);
  rpc Wake(WakeRequest) returns (Ack);
  rpc KeepAlive(KeepAliveRequest) returns (Ack);
}

message StreamRequest { enum Mode { WEBRTC=0; MJPEG=1; } }
message InputMessage { oneof payload { MouseInput mouse; KeyboardInput key; Clipboard clipboard; } }
```

### Capture Pipeline
- **Wayland**
  - Use `xdg-desktop-portal` RemoteDesktop interface
  - PipeWire stream -> encode via GStreamer (H.264 VP8) -> WebRTC
- **X11**
  - `x11grab` via GStreamer or ffmpeg library
  - Real cursor shape capture for sync

### Input Path
- `/dev/uinput` virtual devices (keyboard + mouse)
- Map browser events → Linux keycodes
- Optional: use `libei` once stable for Wayland injection

### Wake & Power
- Maintain inhibitor lock to stop suspend
- Wake sequence:
  - `loginctl unlock-session`
  - `xset dpms force on`, `xset s reset`
  - Mouse jiggle + key press via `/dev/uinput`

## Web Gateway (Flask) Changes
- Replace `/stream` MJPEG endpoint with WebRTC offer/answer signaling
- Input endpoints forward to Host Agent gRPC
- Manage session tokens for agent API
- Add health checks + reconnection logic

### New Endpoints
- `POST /api/webrtc/offer` → returns SDP answer (gateway bridges to agent)
- `POST /api/input` → forwards to agent
- `POST /api/host/wake` → gRPC wake
- `GET /api/agent/health`

## Browser Client Upgrades
- Use WebRTC video element instead of `<img>`
- Acquire pointer lock for accurate mouse (fallback to relative mode)
- Send keyboard events with both `code` and Linux keycode hints
- Cursor overlay using remote metadata (size, hotspot)
- Status HUD for wake/latency/fps

### JS Modules
- `webrtc.js`: handles signaling with Flask, attaches media
- `input.js`: pointer-lock, keyboard mapping, clipboard sync
- `ui.js`: status, controls, wake button

## Security Model
- Host Agent runs locally; communication via Unix socket
- Gateway authenticates using shared secret or mTLS cert
- Browser auth unchanged (sessions/JWT)
- Future WAN support: turn agent into gRPC TLS server + NAT traversal

## Deployment Plan
1. Build host agent binary (`/usr/local/bin/remote_agent`)
2. Install systemd unit:
```
[Unit]
Description=Remote Browser Desktop Agent
After=network.target

[Service]
ExecStart=/usr/local/bin/remote_agent --config /etc/remote_agent.toml
Restart=on-failure
User=root

[Install]
WantedBy=multi-user.target
```
3. Provide `/etc/remote_agent.toml` with settings (capture mode, secrets)
4. Flask app communicates with agent; UI served via existing HTTP

## Phase Deliverables
- [ ] Finalize API definitions
- [ ] Select language + libraries (Rust: tokio + tonic + pipewire)
- [ ] Scaffold agent project + systemd unit
- [ ] Implement minimal capture & input (unlocked session)
- [ ] Integrate WebRTC signaling path
- [ ] Upgrade frontend to WebRTC + pointer lock
- [ ] End-to-end test (LAN)

Phase 1 = architecture & scaffolding. Phase 2+ will implement and iterate.

