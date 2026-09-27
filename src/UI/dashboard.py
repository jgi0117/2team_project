"""Run the combined dashboard with python -m src.UI.dashboard."""

from pathlib import Path

import dash_bootstrap_components as dbc
from dash import Dash, Input, Output, dcc, html

from .pages.detail import layout as detail_layout
from .sidebar import create_sidebar
from .statistics_page import create_statistics_page


def create_detail_page():
    return html.Div(
        [create_sidebar(equipment_href="/detail", active="equipment"), detail_layout],
        className="ui-dashboard ui-dashboard--detail",
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
    app.layout = html.Div([dcc.Location(id="ui-location"), html.Div(id="ui-page")])

    @app.callback(Output("ui-page", "children"), Input("ui-location", "pathname"))
    def display_page(pathname):
        if pathname == "/detail":
            return create_detail_page()
        return create_statistics_page()

    return app


app = create_app()
server = app.server


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=8050)
