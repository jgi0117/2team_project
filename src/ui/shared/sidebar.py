"""Navigation shared by the main, equipment, and statistics pages."""

from dash import dcc, html


def create_sidebar(active="main"):
    def menu(label, href, selected=False):
        if selected:
            return html.Span(
                label,
                className="ui-nav-item ui-nav-item--active",
                **{"aria-current": "page"},
            )
        return dcc.Link(label, href=href, className="ui-nav-item")

    return html.Aside(
        html.Nav(
            [
                menu("메인화면", "/", active == "main"),
                menu("설비별", "/detail", active == "equipment"),
                menu("통계", "/statistics", active == "statistics"),
            ],
            **{"aria-label": "대시보드 메뉴"},
        ),
        className="ui-sidebar",
    )
