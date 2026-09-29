"""Run the combined dashboard with python -m src.ui.app."""

from pathlib import Path
from urllib.parse import parse_qs

import dash_bootstrap_components as dbc
from dash import Dash, Input, Output, ctx, dcc, html
from dash.exceptions import PreventUpdate

from .pages.main import create_main_layout
from .pages.detail.page import MACHINES, create_detail_layout
from .pages.statistics.page import create_statistics_page
from .pages.order.page import create_order_page
from .shared.sidebar import create_sidebar
from .config import UI_AS_OF, valid_as_of


def selected_machine(search):
    try:
        machine_id = int(parse_qs((search or "").lstrip("?")).get("machine", [None])[0])
    except (TypeError, ValueError):
        return None
    return machine_id if machine_id in MACHINES else None


def machine_from_click(click_data):
    try:
        machine_id = click_data["points"][0]["customdata"]
        if isinstance(machine_id, (list, tuple)):
            machine_id = machine_id[0]
        if isinstance(machine_id, bool):
            raise ValueError
        machine_id = int(machine_id)
    except (KeyError, IndexError, TypeError, ValueError):
        raise PreventUpdate
    if machine_id not in MACHINES:
        raise PreventUpdate
    return machine_id


def create_detail_page(machine_id=None, as_of=UI_AS_OF):
    return html.Div(
        [create_sidebar(active="equipment", as_of=as_of),
         create_detail_layout(machine_id, as_of)],
        className="ui-dashboard ui-dashboard--detail",
    )


def create_main_page(as_of=UI_AS_OF):
    return html.Div(
        [create_sidebar(active="main", as_of=as_of), create_main_layout(as_of)],
        className="ui-dashboard ui-dashboard--main",
    )


def create_app():
    app = Dash(
        __name__,
        assets_folder=str(Path(__file__).resolve().parent / "assets"),
        title="설비보전 대시보드",
        external_stylesheets=[dbc.themes.BOOTSTRAP],
        suppress_callback_exceptions=True,
        meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
    )
    app.layout = html.Div([
        dcc.Location(id="ui-location", refresh="callback-nav"),
        # 사이드바에서 고른 기준일. 모든 화면이 이 날짜 기준으로 다시 그려진다.
        dcc.Store(id="store-as-of", storage_type="session", data=UI_AS_OF),
        # 메인 To-Do/TOP5에서 처리 완료(삭제)한 항목 key 목록. 페이지를 옮겨도 유지된다.
        dcc.Store(id="store-todo-dismissed", storage_type="session", data=[]),
        # 설비 상세에서 넣은 발주 기록. 메인 '과거 대응률'이 이 목록만큼 누적된다.
        dcc.Store(id="store-order-log", storage_type="session", data=[]),
        # 설비 상세에서 '발주 정보 보기'로 쌓은 부품 목록 (장바구니). 발주 요청 전 단계.
        dcc.Store(id="store-order-cart", storage_type="session", data=[]),
        # 발주 화면 장바구니: 설비·부품·협력사별 수량. 설비 화면 '발주 담기'로 쌓인다.
        dcc.Store(id="store-order-basket", storage_type="session", data=[]),
        html.Div(id="ui-page"),
    ])

    @app.callback(
        Output("ui-page", "children"),
        Input("ui-location", "pathname"),
        Input("ui-location", "search"),
        Input("store-as-of", "data"),
    )
    def display_page(pathname, search, as_of):
        as_of = valid_as_of(as_of)
        if pathname == "/detail":
            return create_detail_page(selected_machine(search), as_of)
        if pathname == "/statistics":
            return create_statistics_page(as_of)
        if pathname == "/order":
            return create_order_page(as_of)
        return create_main_page(as_of)

    @app.callback(
        Output("ui-location", "pathname"),
        Output("ui-location", "search"),
        Input("f09-heatmap", "clickData", allow_optional=True),
        Input("f10-heatmap", "clickData", allow_optional=True),
        Input("mn-f01-graph", "clickData", allow_optional=True),
        prevent_initial_call=True,
    )
    def open_machine(f09_click, f10_click, surge_click):
        click_data = {"f09-heatmap": f09_click, "f10-heatmap": f10_click,
                      "mn-f01-graph": surge_click}.get(ctx.triggered_id)
        machine_id = machine_from_click(click_data)
        return "/detail", f"?machine={machine_id}"

    return app


app = create_app()
server = app.server


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=8050)
