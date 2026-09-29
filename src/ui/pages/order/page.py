"""발주 화면: 설비 화면에서 '발주 담기'한 부품을 장바구니처럼 모아 한 번에 발주 요청한다.

담긴 줄(store-order-basket)은 설비·부품·협력사 단위. 화면은 부품별 총수량으로 묶고
그 아래에 어느 설비에 몇 개인지 나눠 보여준다.
"""

from collections import OrderedDict

from dash import html, dcc, Input, Output, State, ALL, callback, ctx
from dash.exceptions import PreventUpdate

from src.ui import detail_data
from src.ui.config import UI_AS_OF, valid_as_of
from src.ui.sample_data import ranked_items
from src.ui.shared.sidebar import create_sidebar

COMPS = ["comp1", "comp2", "comp3", "comp4"]


def won(value):
    return f"{value:,.0f}만원"


def create_order_layout(as_of=UI_AS_OF):
    return html.Main(className="page-order", children=[
        dcc.Store(id="od-last-submit"),
        dcc.Store(id="od-init", data=True),   # 페이지가 열릴 때 요청 내역을 그리기 위한 트리거
        dcc.ConfirmDialog(id="od-confirm-dismiss"),
        html.Div([
            html.Div([html.H1("발주"), html.P("설비 화면에서 담은 부품을 부품별로 모아 한 번에 발주 요청합니다.",
                                              className="od-sub")]),
            html.Div([
                dcc.Link("← 설비 화면으로", href="/detail", className="od-btn"),
                html.Button("비우기", id="od-clear", n_clicks=0, className="od-btn"),
                html.Button("발주 요청", id="od-submit", n_clicks=0, className="od-btn od-btn--primary"),
            ], className="od-actions"),
        ], className="od-head"),
        html.Div(id="od-summary", className="od-summary"),
        html.Div(id="od-body"),
        html.Section([
            html.Div(html.H2("발주 요청 내역"), className="od-section-head"),
            html.Div(id="od-history"),
        ], className="od-band"),
        html.Small(f"기준일 {as_of} · 단가·납기는 가상 운영 데이터 기반 예시이며, 발주 요청은 이 브라우저 세션에만 기록됩니다.",
                   className="od-note"),
    ])


def create_order_page(as_of=UI_AS_OF):
    return html.Div([create_sidebar(active="order", as_of=as_of), create_order_layout(as_of)],
                    className="ui-dashboard ui-dashboard--order")


def stepper(key, qty):
    return html.Div([
        html.Button("−", id={"type": "od-dec", "key": key}, className="od-step", **{"aria-label": "1개 줄이기"}),
        html.Span(str(qty), className="od-qty"),
        html.Button("+", id={"type": "od-inc", "key": key}, className="od-step", **{"aria-label": "1개 늘리기"}),
    ], className="od-stepper")


@callback(
    Output("od-summary", "children"),
    Output("od-body", "children"),
    Input("store-order-basket", "data"),
    State("store-as-of", "data"),
)
def render_basket(basket, as_of):
    basket = basket or []
    as_of = valid_as_of(as_of)
    if not basket:
        empty = html.Div([
            html.Strong("담긴 부품이 없습니다"),
            html.Span("설비 화면 → 발주 시점 · 비용 검토 → '발주 목록 담기' → 협력사별 수량을 정해 '발주 담기'를 누르세요."),
            dcc.Link("설비 화면으로 가기 →", href="/detail", className="od-link"),
        ], className="od-empty")
        return [], empty

    groups = OrderedDict((comp, []) for comp in COMPS)
    for line in basket:
        groups.setdefault(line["comp"], []).append(line)

    total_qty = sum(line["qty"] for line in basket)
    total_cost = sum(line["qty"] * line["price"] for line in basket)
    machines = len({line["machine"] for line in basket})
    summary = [
        html.Div([html.Span("담은 부품"), html.Strong(f"{sum(1 for lines in groups.values() if lines)}종")], className="od-kpi"),
        html.Div([html.Span("총 수량"), html.Strong(f"{total_qty}개")], className="od-kpi"),
        html.Div([html.Span("대상 설비"), html.Strong(f"{machines}대")], className="od-kpi"),
        html.Div([html.Span("예상 금액"), html.Strong(won(total_cost))], className="od-kpi is-accent"),
    ]

    cards = []
    for comp, lines in groups.items():
        if not lines:
            continue
        qty = sum(line["qty"] for line in lines)
        cost = sum(line["qty"] * line["price"] for line in lines)
        rows = [html.Tr([
            html.Td(dcc.Link(f"M-{line['machine']:03d}", href=f"/detail?machine={line['machine']}", className="od-link")),
            html.Td(line["supplier_name"]),
            html.Td(f"{line['lead']}일"),
            html.Td(won(line["price"])),
            html.Td(stepper(line["key"], line["qty"])),
            html.Td(won(line["qty"] * line["price"]), className="od-num"),
            html.Td(html.Button("✕", id={"type": "od-remove", "key": line["key"]}, className="od-icon-btn",
                                title="빼기", **{"aria-label": "빼기"})),
        ]) for line in sorted(lines, key=lambda line: line["machine"])]
        breakdown = " · ".join(f"M-{line['machine']:03d} {line['qty']}개" for line in sorted(lines, key=lambda l: l["machine"]))
        cards.append(html.Section(className="od-card", children=[
            html.Div([
                html.Div([html.H2(comp), html.Span(breakdown, className="od-breakdown")]),
                html.Div([html.Span("총"), html.Strong(f"{qty}개"), html.Span(won(cost), className="od-card-cost")],
                         className="od-card-total"),
            ], className="od-card-head"),
            html.Div(html.Table([
                html.Thead(html.Tr([html.Th(name) for name in ("설비", "협력사", "납기", "단가", "수량", "금액", "")])),
                html.Tbody(rows),
            ], className="od-table"), className="od-scroll"),
        ]))
    return summary, html.Div(cards, className="od-cards")


@callback(
    Output("store-order-basket", "data", allow_duplicate=True),
    Input({"type": "od-inc", "key": ALL}, "n_clicks"),
    Input({"type": "od-dec", "key": ALL}, "n_clicks"),
    Input({"type": "od-remove", "key": ALL}, "n_clicks"),
    Input("od-clear", "n_clicks"),
    State("store-order-basket", "data"),
    prevent_initial_call=True,
)
def edit_basket(_inc, _dec, _remove, _clear, basket):
    if not ctx.triggered or not ctx.triggered[0]["value"]:
        raise PreventUpdate
    trig = ctx.triggered_id
    if trig == "od-clear":
        return []
    basket = list(basket or [])
    result = []
    for line in basket:
        if line["key"] != trig["key"]:
            result.append(line)
        elif trig["type"] == "od-inc":
            result.append({**line, "qty": line["qty"] + 1})
        elif trig["type"] == "od-dec" and line["qty"] > 1:
            result.append({**line, "qty": line["qty"] - 1})
        elif trig["type"] == "od-dec":
            result.append(line)            # 1개 아래로는 줄이지 않음 (빼기는 ✕)
    return result


# TODO(기능): 실제 발주 시스템과 연결. 지금은 세션의 발주 기록(store-order-log)에만 남긴다.
@callback(
    Output("store-order-log", "data"),
    Output("store-order-basket", "data", allow_duplicate=True),
    Output("od-last-submit", "data"),
    Input("od-submit", "n_clicks"),
    State("store-order-basket", "data"),
    State("store-order-log", "data"),
    State("store-as-of", "data"),
    prevent_initial_call=True,
)
def submit(n_clicks, basket, log, as_of):
    if not n_clicks or not basket:
        raise PreventUpdate
    date = valid_as_of(as_of)
    orders = [{"machine": line["machine"], "component": line["comp"], "supplier": line["supplier"],
               "supplier_name": line["supplier_name"], "qty": line["qty"], "price": line["price"], "date": date}
              for line in basket]
    return [*(log or []), *orders], [], orders


@callback(
    Output("od-history", "children"),
    Input("store-order-log", "data"),
    Input("od-init", "data"),
)
def render_history(log, _init=None):
    log = [order for order in (log or []) if "qty" in order]
    if not log:
        return html.Div("아직 발주 요청한 내역이 없습니다.", className="od-empty-line")
    return html.Div(html.Table([
        html.Thead(html.Tr([html.Th(name) for name in ("요청일", "설비", "부품", "협력사", "수량", "금액", "상태")])),
        html.Tbody([html.Tr([
            html.Td(order["date"]), html.Td(f"M-{order['machine']:03d}"), html.Td(order["component"]),
            html.Td(order.get("supplier_name", order["supplier"])), html.Td(f"{order['qty']}개"),
            html.Td(won(order["qty"] * order["price"]), className="od-num"),
            html.Td(html.Span("요청 완료", className="od-status")),
        ]) for order in reversed(log)]),
    ], className="od-table"), className="od-scroll od-history-table")


def top5_matches(orders, dismissed, as_of):
    top = ranked_items(dismissed, as_of=valid_as_of(as_of))[:5]
    ordered = {(order["machine"], order["component"]) for order in orders or []}
    return [item for item in top
            if (item["machine"], item.get("component")) in ordered
            or (item.get("component") is None and any(m == item["machine"] for m, _ in ordered))]


@callback(
    Output("od-confirm-dismiss", "displayed"),
    Output("od-confirm-dismiss", "message"),
    Input("od-last-submit", "data"),
    State("store-todo-dismissed", "data"),
    State("store-as-of", "data"),
    prevent_initial_call=True,
)
def ask_dismiss(orders, dismissed, as_of):
    matches = top5_matches(orders, dismissed, as_of)
    if not matches:
        raise PreventUpdate
    names = ", ".join(f"M-{item['machine']:03d}" + (f" {item['component']}" if item.get("component") else "")
                      for item in matches)
    return True, (f"발주를 요청했습니다.\n{names}이(가) 메인 화면 '우선 확인 설비 TOP5'에 있습니다.\n"
                  "우선순위에서 삭제하시겠습니까?")


@callback(
    Output("store-todo-dismissed", "data", allow_duplicate=True),
    Input("od-confirm-dismiss", "submit_n_clicks"),
    State("od-last-submit", "data"),
    State("store-todo-dismissed", "data"),
    State("store-as-of", "data"),
    prevent_initial_call=True,
)
def dismiss(submitted, orders, dismissed, as_of):
    matches = top5_matches(orders, dismissed, as_of)
    if not submitted or not matches:
        raise PreventUpdate
    return list(dict.fromkeys([*(dismissed or []), *(item["key"] for item in matches)]))


def basket_line(machine, comp, supplier, qty):
    """설비 화면의 '발주 담기'가 만드는 한 줄."""
    return {"key": f"{machine}-{comp}|{supplier['id']}", "machine": machine, "comp": comp,
            "supplier": supplier["id"], "supplier_name": supplier["name"], "lead": supplier["lead"],
            "price": supplier["price"], "qty": qty}


def add_line(basket, line):
    """같은 설비·부품·협력사면 수량을 더하고, 아니면 새 줄."""
    basket = list(basket or [])
    for i, row in enumerate(basket):
        if row["key"] == line["key"]:
            basket[i] = {**row, "qty": row["qty"] + line["qty"]}
            return basket
    return [*basket, line]


SUPPLIERS = {comp: {s["id"]: s for s in detail_data.suppliers_for(comp)} for comp in COMPS}
