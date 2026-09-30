from __future__ import annotations

import hmac
import os
import secrets
from datetime import timedelta
from html import escape
from urllib.parse import urlsplit

from flask import redirect, render_template_string, request, session, url_for
from sqlalchemy import text

from .auth import authenticate, create_admin, has_users
from .connection import SessionLocal, enabled
from .models import ErrorLog


PAGE = """<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{ title }}</title><style>
:root{--navy:#001d3d;--blue:#003566;--yellow:#ffc300;--ink:#001429}*{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;font-family:Arial,'Malgun Gothic',sans-serif;color:var(--ink);background:radial-gradient(circle at 15% 20%,#0b4c82 0,transparent 32%),linear-gradient(135deg,#000814,var(--navy) 55%,var(--blue))}body:before{content:'';position:fixed;inset:0;opacity:.12;background-image:linear-gradient(#fff 1px,transparent 1px),linear-gradient(90deg,#fff 1px,transparent 1px);background-size:34px 34px}.shell{position:relative;width:min(940px,calc(100% - 32px));min-height:540px;display:grid;grid-template-columns:1.08fr .92fr;border-radius:24px;overflow:hidden;box-shadow:0 30px 90px #0008;background:#fff}.visual{padding:54px;color:#fff;background:linear-gradient(145deg,#001d3d,#003566);display:flex;flex-direction:column;justify-content:space-between}.brand{font-weight:900;font-size:22px}.brand b{display:inline-grid;place-items:center;width:42px;height:42px;margin-right:10px;border-radius:12px;background:var(--yellow);color:var(--navy)}.visual h2{font-size:40px;line-height:1.18;margin:0}.visual p{color:#c9ddf1;line-height:1.7}.panel{padding:58px 52px;display:grid;align-content:center}.eyebrow{color:var(--blue);font-weight:800}.panel h1{font-size:32px;margin:10px 0}.lead{color:#5c6f82;margin:0 0 28px}.field{margin:16px 0}.field label{display:block;font-size:13px;font-weight:800;margin-bottom:7px}.field input{width:100%;height:48px;border:1px solid #cad5e0;border-radius:10px;padding:0 14px;font-size:15px}.field input:focus{outline:3px solid #ffc30055;border-color:var(--yellow)}button{width:100%;height:50px;border:0;border-radius:10px;background:var(--navy);color:#fff;font-weight:900;font-size:15px;cursor:pointer}button:hover{background:var(--blue)}.error{padding:11px 13px;border-radius:8px;background:#fff0f0;color:#b42318;font-size:13px}.note{display:block;margin-top:18px;color:#708090;font-size:12px;line-height:1.5}@media(max-width:720px){.shell{display:block;min-height:0}.visual{display:none}.panel{padding:42px 28px}}
</style></head><body><div class="shell"><section class="visual"><div class="brand"><b>PM</b>설비보전</div><div><h2>설비 상태를 확인하고<br>필요한 조치를<br>한곳에서.</h2><p>설비 위험, 재고와 발주, 조치 이력을 한 화면에서 확인합니다.</p></div><small>Predictive Maintenance Dashboard</small></section><main class="panel"><span class="eyebrow">{{ eyebrow }}</span><h1>{{ title }}</h1><p class="lead">{{ lead }}</p>{% if error %}<div class="error">{{ error }}</div>{% endif %}<form method="post"><input type="hidden" name="csrf" value="{{ csrf }}"><input type="hidden" name="next" value="{{ next_path }}"><div class="field"><label for="username">사용자명</label><input id="username" name="username" autocomplete="username" required autofocus></div><div class="field"><label for="password">비밀번호</label><input id="password" name="password" type="password" autocomplete="{{ autocomplete }}" required></div>{% if setup %}<div class="field"><label for="confirm">비밀번호 확인</label><input id="confirm" name="confirm" type="password" autocomplete="new-password" required></div>{% endif %}<button type="submit">{{ button }}</button></form><small class="note">승인된 계정으로 로그인해 설비 현황과 운영 기록을 확인하세요.</small></main></div></body></html>"""


def _safe_next(value: str | None) -> str:
    value = value or "/"
    parsed = urlsplit(value)
    return value if not parsed.scheme and not parsed.netloc and value.startswith("/") and not value.startswith("//") else "/"


def _local_request() -> bool:
    return (request.remote_addr or "") in {"127.0.0.1", "::1"}


def configure(server) -> None:
    if not enabled() or os.getenv("AUTH_ENABLED", "true").lower() not in {"1", "true", "yes", "on"}:
        return
    secret = os.getenv("AUTH_SECRET_KEY", "")
    if len(secret) < 32:
        raise RuntimeError("AUTH_SECRET_KEY must contain at least 32 characters")
    server.config.update(SECRET_KEY=secret, PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
                         SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")

    @server.before_request
    def require_login():
        if request.path.startswith("/assets/") or request.endpoint in {"ge_login", "ge_setup"}:
            return None
        if not has_users():
            if _local_request():
                return redirect(url_for("ge_setup"))
            return "관리자 계정이 아직 생성되지 않았습니다. 서버 PC에서 먼저 설정하세요.", 503
        if session.get("user_id"):
            return None
        return redirect(url_for("ge_login", next=_safe_next(request.full_path)))

    @server.route("/setup", methods=["GET", "POST"], endpoint="ge_setup")
    def setup():
        if has_users():
            return redirect(url_for("ge_login"))
        if not _local_request():
            return "초기 관리자 생성은 서버 PC에서만 가능합니다.", 403
        csrf = session.setdefault("csrf", secrets.token_urlsafe(32))
        error = None
        if request.method == "POST":
            if not hmac.compare_digest(csrf, request.form.get("csrf", "")):
                error = "요청이 만료되었습니다. 다시 시도하세요."
            elif request.form.get("password") != request.form.get("confirm"):
                error = "비밀번호 확인이 일치하지 않습니다."
            else:
                try:
                    create_admin(request.form.get("username", ""), request.form.get("password", ""))
                    return redirect(url_for("ge_login"))
                except ValueError as exc:
                    error = str(exc)
        return render_template_string(PAGE, title="관리자 계정 생성", eyebrow="FIRST SETUP",
                                      lead="대시보드에서 사용할 첫 관리자 계정을 만드세요.", error=error,
                                      csrf=csrf, next_path="/", setup=True, button="관리자 생성",
                                      autocomplete="new-password")

    @server.route("/login", methods=["GET", "POST"], endpoint="ge_login")
    def login():
        if not has_users():
            return redirect(url_for("ge_setup"))
        csrf = session.setdefault("csrf", secrets.token_urlsafe(32))
        next_path = _safe_next(request.args.get("next") or request.form.get("next"))
        error = None
        if request.method == "POST":
            if not hmac.compare_digest(csrf, request.form.get("csrf", "")):
                error = "요청이 만료되었습니다. 다시 시도하세요."
            else:
                user = authenticate(request.form.get("username", ""), request.form.get("password", ""),
                                    request.remote_addr or "unknown")
                if user:
                    session.clear(); session.permanent = True
                    session.update(user_id=user.user_id, username=user.username, is_admin=user.is_admin)
                    return redirect(next_path)
                error = "사용자명 또는 비밀번호를 확인하세요."
        return render_template_string(PAGE, title="대시보드 로그인", eyebrow="WELCOME BACK",
                                      lead="승인된 계정으로 설비 현황을 확인하세요.", error=error,
                                      csrf=csrf, next_path=next_path, setup=False, button="로그인",
                                      autocomplete="current-password")

    @server.route("/logout", endpoint="ge_logout")
    def logout():
        session.clear()
        return redirect(url_for("ge_login"))

    @server.after_request
    def secure_headers(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        return response


def log_error(error: BaseException, path: str, owner_key: str) -> None:
    if not enabled():
        return
    try:
        with SessionLocal.begin() as db:
            db.add(ErrorLog(owner_key=owner_key, path=path[:255], error_type=type(error).__name__[:120],
                            message=str(error)[:4000]))
    except Exception:
        pass
