"""Statistics page layout for the shared dashboard."""

from dash import html

from ...shared.sidebar import create_sidebar
from .layout import create_statistics_layout


def create_statistics_page():
    return html.Div(
        [create_sidebar(active="statistics"), create_statistics_layout()],
        className="ui-dashboard ui-dashboard--statistics",
    )
