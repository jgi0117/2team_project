"""Flask session authentication protecting the Dash application."""

from __future__ import annotations

import hmac
import os
import secrets
from datetime import timedelta
from urllib.parse import urlsplit

from flask import redirect, render_template_string, request, session, url_for

from src.database.auth import authenticate


LOGIN_TEMPLATE = """<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>설비보전 대시보드 로그인</title>
  <style>
    :root { font-family: Arial, "Noto Sans KR", sans-serif; color: #17233b; background: #eef2f6; }
    * { box-sizing: border-box; }
    body { min-height: 100vh; margin: 0; display: grid; place-items: center; padding: 20px; }
    main { width: min(420px, 100%); padding: 34px; border-radius: 18px; background: white;
           box-shadow: 0 18px 55px rgba(19, 33, 56, .15); }
    .mark { display: grid; place-items: center; width: 42px; height: 42px; border-radius: 12px;
            background: #ffd84d; font-weight: 900; }
    h1 { margin: 18px 0 6px; font-size: 24px; }
    p { margin: 0 0 24px; color: #667085; font-size: 14px; }
    label { display: block; margin: 14px 0 6px; font-size: 13px; font-weight: 700; }
    input { width: 100%; height: 46px; padding: 0 13px; border: 1px solid #cbd3df;
            border-radius: 10px; font: inherit; }
    input:focus { outline: 2px solid #ffd84d; border-color: #17233b; }
    button { width: 100%; height: 48px; margin-top: 22px; border: 0; border-radius: 10px;
             background: #17233b; color: white; font: inherit; font-weight: 800; cursor: pointer; }
    .error { padding: 11px 13px; border-radius: 9px; background: #fff0f0; color: #b42318; }
    small { display: block; margin-top: 18px; color: #98a2b3; text-align: center; }
  </style>
</head>
<body>
  <main>
    <div class="mark">PM</div>
    <h1>설비보전 대시보드</h1>
    <p>승인된 계정으로 로그인하세요.</p>
    {% if error %}<div class="error" role="alert">{{ error }}</div>{% endif %}
    <form method="post" action="{{ url_for('dashboard_login') }}">
      <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
      <input type="hidden" name="next" value="{{ next_path }}">
      <label for="username">사용자명</label>
      <input id="username" name="username" autocomplete="username" required autofocus>
      <label for="password">비밀번호</label>
      <input id="password" name="password" type="password" autocomplete="current-password" required>
      <button type="submit">로그인</button>
    </form>
    <small>같은 네트워크에서 승인된 사용자만 접근할 수 있습니다.</small>
  </main>
</body>
</html>"""


def authentication_enabled() -> bool:
    return os.getenv("AUTH_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}


def _safe_next(value: str | None) -> str:
    value = value or "/"
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc or not parsed.path.startswith("/") or parsed.path.startswith("//"):
        return "/"
    return value


def configure_authentication(server) -> None:
    if not authentication_enabled():
        return
    secret_key = os.getenv("AUTH_SECRET_KEY", "")
    if len(secret_key) < 32:
        raise RuntimeError("AUTH_SECRET_KEY must contain at least 32 characters")
    server.config.update(
        SECRET_KEY=secret_key,
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=False,  # LAN deployment currently uses HTTP.
    )

    @server.before_request
    def require_dashboard_login():
        if request.endpoint in {"dashboard_login"}:
            return None
        if session.get("user_id"):
            return None
        return redirect(url_for("dashboard_login", next=_safe_next(request.full_path)))

    @server.route("/login", methods=["GET", "POST"], endpoint="dashboard_login")
    def dashboard_login():
        if session.get("user_id"):
            return redirect(_safe_next(request.args.get("next") or request.form.get("next")))
        csrf_token = session.get("login_csrf") or secrets.token_urlsafe(32)
        session["login_csrf"] = csrf_token
        error = None
        next_path = _safe_next(request.args.get("next") or request.form.get("next"))
        if request.method == "POST":
            submitted = request.form.get("csrf_token", "")
            if not hmac.compare_digest(csrf_token, submitted):
                error = "요청이 만료되었습니다. 다시 시도하세요."
            else:
                result = authenticate(
                    request.form.get("username", ""),
                    request.form.get("password", ""),
                    request.remote_addr or "unknown",
                    request.user_agent.string,
                )
                if result.success:
                    session.clear()
                    session.permanent = True
                    session["user_id"] = result.user_id
                    session["username"] = result.username
                    session["is_admin"] = result.is_admin
                    return redirect(next_path)
                error = ("로그인 시도가 잠겼습니다. 15분 후 다시 시도하세요."
                         if result.reason == "locked" else
                         "사용자명 또는 비밀번호가 올바르지 않습니다.")
        return render_template_string(
            LOGIN_TEMPLATE,
            error=error,
            csrf_token=csrf_token,
            next_path=next_path,
        )

    @server.route("/logout", methods=["GET"], endpoint="dashboard_logout")
    def dashboard_logout():
        session.clear()
        return redirect(url_for("dashboard_login"))

    @server.after_request
    def prevent_private_page_caching(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        return response
