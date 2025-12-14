"""
Lightweight HTTP client that proxies the Flask app to the privileged host agent.

During Phase 2 the agent provides stubbed endpoints so the web gateway can be
developed independently. When REMOTE_AGENT_ENABLED is false the Flask app
falls back to in-process capture and input handling.
"""



from __future__ import annotations

import logging
from typing import Any, Dict

import requests

import config

logger = logging.getLogger(__name__)


class AgentClientError(RuntimeError):
    """Raised when the host agent rejects a request."""


def _headers() -> Dict[str, str]:
    return {
        'Authorization': f'Bearer {config.AGENT_TOKEN}',
        'Content-Type': 'application/json',
    }


def _request(method: str, path: str, json: Dict[str, Any] | None = None) -> Dict[str, Any]:
    url = f'{config.AGENT_BASE_URL}{path}'
    try:
        response = requests.request(
            method=method,
            url=url,
            json=json,
            timeout=config.AGENT_TIMEOUT,
            headers=_headers(),
        )
    except requests.RequestException as exc:
        raise AgentClientError(f'Agent unavailable: {exc}') from exc

    if not response.ok:
        raise AgentClientError(f'Agent error {response.status_code}: {response.text}')
    if response.content:
        return response.json()
    return {}


def agent_enabled() -> bool:
    return config.AGENT_ENABLED


def send_input(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not agent_enabled():
        raise AgentClientError('Agent not enabled')
    return _request('POST', '/api/input', json=payload)


def wake_host() -> Dict[str, Any]:
    if not agent_enabled():
        raise AgentClientError('Agent not enabled')
    return _request('POST', '/api/wake', json={})


def keep_alive() -> Dict[str, Any]:
    if not agent_enabled():
        raise AgentClientError('Agent not enabled')
    return _request('POST', '/api/keepalive', json={})


def health() -> Dict[str, Any]:
    return _request('GET', '/api/health')


