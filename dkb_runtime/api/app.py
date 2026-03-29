"""ASGI app entrypoint (e.g. `uvicorn dkb_runtime.api.app:app`)."""

from dkb_runtime.main import app

__all__ = ["app"]
