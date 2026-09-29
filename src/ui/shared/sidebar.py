"""Navigation shared by the main, equipment, and statistics pages."""

from dash import dcc, html


def create_sidebar(active="main"):
    def menu(icon, label, href, selected=False):
        children = [html.Span(icon, className="ui-nav-icon", **{"aria-hidden": "true"}),
                    html.Span(label, className="ui-nav-text")]
        if selected:
            return html.Span(
                children,
                className="ui-nav-item ui-nav-item--active",
                title=label,
                **{"aria-current": "page"},
            )
        return dcc.Link(children, href=href, className="ui-nav-item", title=label)

    return html.Aside(
        [
            html.Div([html.Span("⚙", className="ui-brand-mark", **{"aria-hidden": "true"}),
                      html.Span("설비보전", className="ui-brand-text")],
                     className="ui-brand"),
            html.Nav(
                [
                    menu("🏠", "메인화면", "/", active == "main"),
                    menu("🛠", "설비별", "/detail", active == "equipment"),
                    menu("📊", "통계", "/statistics", active == "statistics"),
                ],
                **{"aria-label": "대시보드 메뉴"},
            ),
        ],
        className="ui-sidebar",
    )
