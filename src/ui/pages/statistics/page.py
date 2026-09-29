"""Statistics page layout for the shared dashboard."""

from dash import html

from ...shared.sidebar import create_sidebar
from ...config import UI_AS_OF
from .layout import create_statistics_layout


def create_statistics_page(as_of=UI_AS_OF):
    return html.Div(
        [create_sidebar(active="statistics", as_of=as_of), create_statistics_layout(as_of=as_of)],
        className="ui-dashboard ui-dashboard--statistics",
    )
