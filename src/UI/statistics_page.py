"""Statistics page layout for the shared dashboard."""

from dash import html

from .sidebar import create_sidebar
from .statistics import create_statistics_layout


def create_statistics_page():
    return html.Div(
        [create_sidebar(equipment_href="/detail"), create_statistics_layout()],
        className="ui-dashboard ui-dashboard--statistics",
    )
