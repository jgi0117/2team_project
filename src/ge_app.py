"""GE dashboard plus the fresh, isolated MySQL layer."""

from __future__ import annotations

import os

from dash import dcc
from flask import got_request_exception, request, session

from src.ge_db.bridge import register
from src.ge_db.web import configure, log_error
from src.ui.app import app


configure(app.server)
children = list(app.layout.children)
children.insert(-1, dcc.Store(id="ge-db-sync", storage_type="memory", data={}))
app.layout.children = children
register(app)


def _capture_exception(_sender, exception, **_extra):
    owner = f"user:{session.get('user_id')}" if session.get("user_id") else "anonymous"
    log_error(exception, request.path, owner)


got_request_exception.connect(_capture_exception, app.server, weak=False)
server = app.server


if __name__ == "__main__":
    app.run(
        debug=os.getenv("DASH_DEBUG", "false").lower() in {"1", "true", "yes", "on"},
        host=os.getenv("DASH_HOST", "127.0.0.1"),
        port=int(os.getenv("DASH_PORT", "8050")),
    )
