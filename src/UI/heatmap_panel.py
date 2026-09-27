"""The same single-line heading and bounded plot area for both heatmaps."""

from dash import dcc, html


def panel_contents(*, title, title_id, meaning, date, graph_id, figure, anomaly=False):
    return [
        html.Header([
            html.H2(title, id=title_id),
            html.Span(meaning, className="risk-meaning"),
            html.Div([
                html.Span("낮음"),
                html.Span(className="risk-gradient risk-gradient--anomaly" if anomaly else "risk-gradient"),
                html.Span("높음"),
            ], className="risk-legend", title="붉을수록 위험도가 높습니다. 회색은 결과 없음입니다.",
                **{"aria-label": "위험도 범례: 옅은 파랑은 낮음, 빨강은 높음, 회색은 결과 없음"}),
            html.Time(date, dateTime=date, className="risk-date"),
        ], className="risk-heading"),
        html.Div(
            dcc.Graph(id=graph_id, figure=figure, responsive=True,
                      config={"displayModeBar": False, "scrollZoom": False},
                      className="risk-plot", style={"width": "100%", "height": "100%"}),
            className="risk-plot-frame",
        ),
    ]
