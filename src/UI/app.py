"""Run from the repository root: python -m src.UI.app."""

from pathlib import Path

from dash import Dash, html

from .sidebar import create_sidebar
from .statistics import create_statistics_layout


def create_app():
    app = Dash(
        __name__,
        assets_folder=str(Path(__file__).resolve().parent / "assets"),
        title="설비보전 대시보드 · 통계",
    )
    app.layout = html.Div(
        [create_sidebar(), create_statistics_layout()],
        className="ui-dashboard",
    )
    return app


app = create_app()
server = app.server


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=8050)
