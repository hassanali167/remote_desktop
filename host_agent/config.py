from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel


class AgentSettings(BaseModel):
    bind: str = os.environ.get('HOST_AGENT_BIND', '127.0.0.1')
    port: int = int(os.environ.get('HOST_AGENT_PORT', 8787))
    token: str = os.environ.get('HOST_AGENT_TOKEN', 'replace-this-agent-token')
    log_level: str = os.environ.get('HOST_AGENT_LOG_LEVEL', 'INFO')
    state_dir: Path = Path(os.environ.get('HOST_AGENT_STATE_DIR', '/tmp/host_agent'))
    enable_stub_capture: bool = os.environ.get('HOST_AGENT_STUB_CAPTURE', 'true').lower() in {'1', 'true', 'yes'}


settings = AgentSettings()

