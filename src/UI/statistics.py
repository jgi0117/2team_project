"""Two equipment overviews: sensor anomalies above failure risk."""

from dash import html

from src.F09.dashboard import create_layout
from src.F09.heatmap import load_predictions
from src.F10.dashboard import create_layout as create_anomaly_layout


def create_statistics_layout(predictions=None):
    predictions = load_predictions() if predictions is None else predictions
    return html.Main(
        [
            html.H1("통계", className="ui-sr-only"),
            html.Section(
                create_anomaly_layout(predictions.as_of.max()),
                id="stats-f10-content", className="risk-panel",
                **{"aria-labelledby": "stats-f10-title"},
            ),
            html.Section(
                create_layout(predictions),
                id="stats-f09-content",
                className="risk-panel",
                **{"aria-labelledby": "stats-f09-title"},
            ),
        ],
        className="ui-statistics",
        id="statistics-page",
    )
