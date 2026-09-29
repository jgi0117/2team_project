"""설정 창 (사이드바 톱니바퀴): 로그인 기록 · 완료 기록 관리 · 기본 설정."""

from datetime import datetime

import dash_bootstrap_components as dbc
from dash import ALL, Input, Output, State, callback, ctx, dcc, html
from dash.exceptions import PreventUpdate

from src.ui.config import CURRENT_USER
from src.ui.settings import DEFAULTS, SPEC, merged

CONTROL_IDS = [key for _, key, *_ in SPEC]


def _control(key, kind, options, value):
    if kind == "number":
        return dcc.Input(id=f"st-{key}", type="number", value=value, min=options["min"], max=options["max"],
                         step=options["step"], className="st-number", debounce=True)
    return dcc.Dropdown(id=f"st-{key}", options=[{"label": label, "value": v} for v, label in options],
                        value=value, clearable=False, searchable=False, className="st-select")


def defaults_tab(values):
    groups = {}
    for category, key, name, help_text, kind, options in SPEC:
        groups.setdefault(category, []).append(html.Div([
            html.Div([html.Strong(name), html.Small(help_text)], className="st-row-text"),
            _control(key, kind, options, values[key]),
        ], className="st-row"))
    return html.Div([
        *[html.Section([html.H3(category), *rows], className="st-group") for category, rows in groups.items()],
        html.Div([
            html.Span(id="st-save-msg", className="st-msg"),
            html.Button("기본값으로 되돌리기", id="st-reset", n_clicks=0, className="st-btn"),
            html.Button("저장", id="st-save", n_clicks=0, className="st-btn st-btn--primary"),
        ], className="st-actions"),
    ])


def settings_modal(settings=None):
    values = merged(settings)
    return dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle("설정")),
        dbc.ModalBody(dbc.Tabs([
            dbc.Tab(html.Div(id="st-login-body"), label="로그인 기록", tab_id="login"),
            dbc.Tab(html.Div(id="st-done-body"), label="완료 기록 관리", tab_id="done"),
            dbc.Tab(defaults_tab(values), label="기본 설정", tab_id="defaults"),
        ], id="st-tabs", active_tab="defaults", className="st-tabs")),
    ], id="sb-settings-modal", is_open=False, size="lg", centered=True, scrollable=True, className="st-modal")


@callback(
    Output("sb-settings-modal", "is_open"),
    [Output(f"st-{key}", "value") for key in CONTROL_IDS],
    Input("sb-settings-open", "n_clicks"),
    State("store-settings", "data"),
    prevent_initial_call=True,
)
def open_settings(n_clicks, stored):
    """톱니바퀴를 누르면 저장된 값으로 채워서 연다."""
    if not n_clicks:
        raise PreventUpdate
    values = merged(stored)
    return True, *[values[key] for key in CONTROL_IDS]


# ---------------- 로그인 기록 ----------------
@callback(
    Output("store-login-log", "data"),
    Output("store-session-started", "data"),
    Input("ui-location", "pathname"),
    State("store-session-started", "data"),
    State("store-login-log", "data"),
)
def record_access(_pathname, started, log):
    """이 브라우저에서 대시보드를 새로 연 시각을 기록 (로그인 기능이 생기면 서버 DB 기록으로 교체)."""
    if started:
        raise PreventUpdate
    entry = {"at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "user": CURRENT_USER["name"],
             "title": CURRENT_USER["title"], "role": CURRENT_USER["role"]}
    return ([entry] + list(log or []))[:200], True


@callback(
    Output("st-login-body", "children"),
    Input("sb-settings-modal", "is_open"),
    State("store-login-log", "data"),
)
def show_logins(is_open, log):
    if not is_open:
        raise PreventUpdate
    rows = [html.Tr([html.Td(item["at"]), html.Td(item["user"]), html.Td(item["title"]), html.Td(item["role"])])
            for item in log or []]
    return html.Div([
        html.P("이 브라우저에서 대시보드에 접속한 기록입니다. 로그인 기능이 연결되면 계정별 접속 기록(DB)으로 바뀝니다.",
               className="st-desc"),
        html.Div(html.Table([html.Thead(html.Tr([html.Th(n) for n in ("접속 시각", "사용자", "소속·직급", "권한")])),
                             html.Tbody(rows or [html.Tr(html.Td("기록 없음", colSpan=4))])],
                            className="st-table"), className="st-scroll"),
    ])


# ---------------- 완료 기록 관리 ----------------
def _label(key):
    machine, _, part = key.partition("-")
    return f"M-{int(machine):03d} · " + ("센서 이상 점검" if part == "if" else part)


@callback(
    Output("st-done-body", "children"),
    Input("sb-settings-modal", "is_open"),
    Input("store-todo-dismissed", "data"),
    Input("store-order-log", "data"),
)
def show_done(is_open, dismissed, orders):
    if not is_open:
        raise PreventUpdate
    done_rows = [html.Tr([html.Td(_label(key)), html.Td("처리 완료로 To-Do에서 삭제"),
                          html.Td(html.Button("복구", id={"type": "st-restore", "key": key}, n_clicks=0,
                                              className="st-btn st-btn--sm"))])
                 for key in dismissed or []]
    order_rows = [html.Tr([html.Td(order.get("date", "")),
                           html.Td(f"M-{order['machine']:03d} · {order['component']}"),
                           html.Td(f"{order.get('supplier_name', order.get('supplier', ''))} · {order.get('qty', 1)}개"),
                           html.Td(html.Button("요청 취소", id={"type": "st-order-undo", "idx": i}, n_clicks=0,
                                               className="st-btn st-btn--sm"))])
                  for i, order in enumerate(orders or [])]
    return html.Div([
        html.H3("To-Do에서 완료 처리한 항목"),
        html.P("완료했는데 실제로는 처리가 안 됐다면 '복구'를 누르세요. 메인 To-Do와 TOP5에 다시 나타납니다.",
               className="st-desc"),
        html.Div(html.Table([html.Thead(html.Tr([html.Th(n) for n in ("설비 · 부품", "상태", "")])),
                             html.Tbody(done_rows or [html.Tr(html.Td("완료 처리한 항목이 없습니다", colSpan=3))])],
                            className="st-table"), className="st-scroll"),
        html.H3("발주 요청 기록"),
        html.P("발주가 실제로 오지 않았다면 '요청 취소'를 누르세요. 과거 대응률에서도 빠집니다.", className="st-desc"),
        html.Div(html.Table([html.Thead(html.Tr([html.Th(n) for n in ("요청일", "설비 · 부품", "협력사 · 수량", "")])),
                             html.Tbody(order_rows or [html.Tr(html.Td("발주 요청 기록이 없습니다", colSpan=4))])],
                            className="st-table"), className="st-scroll"),
    ])


@callback(
    Output("store-todo-dismissed", "data", allow_duplicate=True),
    Input({"type": "st-restore", "key": ALL}, "n_clicks"),
    State("store-todo-dismissed", "data"),
    prevent_initial_call=True,
)
def restore_done(_clicks, dismissed):
    if not ctx.triggered or not ctx.triggered[0]["value"]:
        raise PreventUpdate
    return [key for key in dismissed or [] if key != ctx.triggered_id["key"]]


@callback(
    Output("store-order-log", "data", allow_duplicate=True),
    Input({"type": "st-order-undo", "idx": ALL}, "n_clicks"),
    State("store-order-log", "data"),
    prevent_initial_call=True,
)
def undo_order(_clicks, orders):
    if not ctx.triggered or not ctx.triggered[0]["value"]:
        raise PreventUpdate
    index = ctx.triggered_id["idx"]
    return [order for i, order in enumerate(orders or []) if i != index]


# ---------------- 기본 설정 ----------------
@callback(
    Output("store-settings", "data"),
    Output("st-save-msg", "children"),
    Input("st-save", "n_clicks"),
    Input("st-reset", "n_clicks"),
    [State(f"st-{key}", "value") for key in CONTROL_IDS],
    prevent_initial_call=True,
)
def save_settings(_save, _reset, *values):
    if not ctx.triggered or not ctx.triggered[0]["value"]:
        raise PreventUpdate
    if ctx.triggered_id == "st-reset":
        return dict(DEFAULTS), "기본값으로 되돌렸습니다. 화면에 바로 반영됩니다."
    saved = merged(dict(zip(CONTROL_IDS, values)))
    return saved, "저장했습니다. 화면에 바로 반영됩니다."
