"""Run from the repository root: python -m src.UI.app."""

from pathlib import Path

from dash import Dash, Input, Output, dcc, html
import dash_bootstrap_components as dbc

from .pages.detail import layout as detail_layout
from .sidebar import create_sidebar
from .statistics import create_statistics_layout


def create_app():
    app = Dash(
        __name__,
        assets_folder=str(Path(__file__).resolve().parent / "assets"),
        title="설비보전 대시보드 · 통계",
        external_stylesheets=[dbc.themes.BOOTSTRAP],
        suppress_callback_exceptions=True,
        meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
    )
    app.layout = html.Div(
        [dcc.Location(id="ui-location"), html.Div(id="ui-page")],
    )

    @app.callback(Output("ui-page", "children"), Input("ui-location", "pathname"))
    def display_page(pathname):
        if pathname == "/detail":
            return html.Div(
                [create_sidebar(equipment_href="/detail", active="equipment"), detail_layout],
                className="ui-dashboard",
            )
        return html.Div(
            [create_sidebar(equipment_href="/detail"), create_statistics_layout()],
            className="ui-dashboard",
        )

    return app


app = create_app()
server = app.server


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=8050)
