"""Shared sidebar; supply destination URLs when the other pages are ready."""

from dash import dcc, html


def create_sidebar(main_href=None, equipment_href=None):
    def menu(label, href):
        if href is None:
            return html.Button(
                label,
                disabled=True,
                className="ui-nav-item",
                title="화면 연결 예정",
                type="button",
            )
        return dcc.Link(label, href=href, className="ui-nav-item")

    return html.Aside(
        html.Nav(
            [
                menu("메인화면", main_href),
                menu("설비별", equipment_href),
                html.Span(
                    "통계",
                    className="ui-nav-item ui-nav-item--active",
                    **{"aria-current": "page"},
                ),
            ],
            **{"aria-label": "대시보드 메뉴"},
        ),
        className="ui-sidebar",
    )
