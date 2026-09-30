"""GE dashboard plus the fresh, isolated MySQL layer."""

from __future__ import annotations

import os
from flask import got_request_exception, request, session

from src.ge_db.bridge import install
from src.ge_db.web import configure, log_error
from src.common.data_source import configure_reader
from src.ge_db.datasets import read_csv

configure_reader(read_csv)
from src.ui.app import app


configure(app.server)
install(app.server)


def _capture_exception(_sender, exception, **_extra):
    owner = f"user:{session.get('user_id')}" if session.get("user_id") else "anonymous"
    log_error(exception, request.path, owner)


got_request_exception.connect(_capture_exception, app.server, weak=False)
server = app.server


def main():
    app.run(
        debug=os.getenv("DASH_DEBUG", "false").lower() in {"1", "true", "yes", "on"},
        host=os.getenv("DASH_HOST", "127.0.0.1"),
        port=int(os.getenv("DASH_PORT", "8050")),
    )


if __name__ == "__main__":
    main()
