"""Slide 14: F10 above F09. Replace panel children with future features."""

from dash import html


def create_statistics_layout():
    return html.Main(
        [
            html.H1("통계", className="ui-sr-only"),
            html.Section(
                html.H2("F10 공정별 이상 위험 히트맵", id="stats-f10-title"),
                id="stats-f10-content",
                className="ui-stat-panel",
                **{"aria-labelledby": "stats-f10-title"},
            ),
            html.Section(
                html.H2("F09 설비별 고장 예측 히트맵", id="stats-f09-title"),
                id="stats-f09-content",
                className="ui-stat-panel",
                **{"aria-labelledby": "stats-f09-title"},
            ),
        ],
        className="ui-statistics",
        id="statistics-page",
    )
