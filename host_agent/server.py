from __future__ import annotations

import logging
import time
from typing import Any, Dict

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from .config import settings

logger = logging.getLogger(__name__)

app = FastAPI(title='Host Agent Stub', version='0.1.0')


def verify_token(request: Request) -> None:
    auth_header = request.headers.get('Authorization', '')
    if auth_header != f'Bearer {settings.token}':
        raise HTTPException(status_code=401, detail='Invalid token')


class InputPayload(BaseModel):
    type: str
    action: str | None = None
    key: str | None = None
    code: str | None = None
    button: str | None = None
    x: float | None = None
    y: float | None = None
    deltaY: float | None = None
    eventType: str | None = None
    double: bool | None = None


class WebRTCOffer(BaseModel):
    sdp: str
    type: str


@app.get('/api/health')
def health() -> Dict[str, Any]:
    return {'status': 'ok', 'time': time.time(), 'stub': True}


@app.post('/api/keepalive')
def keepalive(_: Request = Depends(verify_token)) -> Dict[str, Any]:
    logger.debug('Keepalive ping received')
    return {'status': 'ok'}


@app.post('/api/input')
def input_event(payload: InputPayload, _: Request = Depends(verify_token)) -> Dict[str, Any]:
    logger.info('Stub agent received input: %s', payload.dict())
    return {'status': 'queued'}


@app.post('/api/wake')
def wake(_: Request = Depends(verify_token)) -> Dict[str, Any]:
    logger.info('Stub wake invoked')
    return {'status': 'ok', 'message': 'Stub wake executed'}


@app.post('/api/webrtc/offer')
def negotiate(offer: WebRTCOffer, _: Request = Depends(verify_token)) -> Dict[str, Any]:
    logger.info('Received WebRTC offer (len=%s)', len(offer.sdp))
    # Placeholder answer
    return {'status': 'stub', 'sdp': offer.sdp, 'type': 'answer'}


@app.get('/api/stream/mock')
def mock_stream(_: Request = Depends(verify_token)):
    if not settings.enable_stub_capture:
        raise HTTPException(status_code=404, detail='Mock stream disabled')

    def generate():
        boundary = '--frame'
        while True:
            frame = b'\xff\xd8\xff'  # Dummy JPEG header
            yield b'%s\r\nContent-Type: image/jpeg\r\n\r\n' % boundary.encode()
            yield frame + b'\r\n'
            time.sleep(1)

    return StreamingResponse(generate(), media_type='multipart/x-mixed-replace; boundary=frame')

