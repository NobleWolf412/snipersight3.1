"""ASGI entry point that makes the integrated cockpit the default UI.

The existing ``server:app`` remains the authoritative API and raw chart app.
This wrapper only intercepts the two human-facing routes:

- ``/`` renders the integrated cockpit with the WHY? drawer.
- ``/raw`` renders the original chart UI for direct access and embedding.
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from server import app as core_app

STATIC = Path(__file__).resolve().parent / "static"

app = FastAPI(title="SniperSight Cockpit")


@app.get("/", include_in_schema=False)
def cockpit():
    return FileResponse(
        STATIC / "cockpit.html",
        headers={"Cache-Control": "no-cache, must-revalidate"},
    )


@app.get("/raw", include_in_schema=False)
def raw_cockpit():
    return FileResponse(
        STATIC / "index.html",
        headers={"Cache-Control": "no-cache, must-revalidate"},
    )


# Delegate API, static assets, docs, and every other route to the existing app.
app.mount("/", core_app)
