from __future__ import annotations

import logging

import uvicorn

from .config import settings


def main() -> None:
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
    uvicorn.run(
        'host_agent.server:app',
        host=settings.bind,
        port=settings.port,
        reload=False,
        log_level=settings.log_level.lower(),
    )


if __name__ == '__main__':
    main()

