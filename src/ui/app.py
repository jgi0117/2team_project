"""Run the combined dashboard with python -m src.ui.app."""

from pathlib import Path
from urllib.parse import parse_qs

import dash_bootstrap_components as dbc
from dash import Dash, Input, Output, ctx, dcc, html
from dash.exceptions import PreventUpdate

from .pages.main import create_main_layout
from .pages.detail.page import MACHINES, create_detail_layout
from .pages.statistics.page import create_statistics_page
from .shared.sidebar import create_sidebar


def selected_machine(search):
    try:
        machine_id = int(parse_qs((search or "").lstrip("?")).get("machine", [None])[0])
    except (TypeError, ValueError):
        return None
    return machine_id if machine_id in MACHINES else None


def machine_from_click(click_data):
    try:
        machine_id = click_data["points"][0]["customdata"]
        if isinstance(machine_id, bool):
            raise ValueError
        machine_id = int(machine_id)
    except (KeyError, IndexError, TypeError, ValueError):
        raise PreventUpdate
    if machine_id not in MACHINES:
        raise PreventUpdate
    return machine_id


def create_detail_page(machine_id=None):
    return html.Div(
        [create_sidebar(active="equipment"),
         create_detail_layout(machine_id)],
        className="ui-dashboard ui-dashboard--detail",
    )


def create_main_page():
    return html.Div(
        [create_sidebar(active="main"), create_main_layout()],
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
        html.Div(id="ui-page"),
    ])

    @app.callback(
        Output("ui-page", "children"),
        Input("ui-location", "pathname"),
        Input("ui-location", "search"),
    )
    def display_page(pathname, search):
        if pathname == "/detail":
            return create_detail_page(selected_machine(search))
        if pathname == "/statistics":
            return create_statistics_page()
        return create_main_page()

    @app.callback(
        Output("ui-location", "pathname"),
        Output("ui-location", "search"),
        Input("f09-heatmap", "clickData"),
        Input("f10-heatmap", "clickData"),
        prevent_initial_call=True,
    )
    def open_machine(f09_click, f10_click):
        click_data = f09_click if ctx.triggered_id == "f09-heatmap" else f10_click
        machine_id = machine_from_click(click_data)
        return "/detail", f"?machine={machine_id}"

    return app


app = create_app()
server = app.server


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=8050)
