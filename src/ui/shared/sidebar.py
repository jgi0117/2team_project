"""Navigation shared by the main, equipment, and statistics pages."""

from pathlib import Path

from dash import Input, Output, State, callback, ctx, dcc, html
from dash.exceptions import PreventUpdate

from src.ui.config import AS_OF_MAX, AS_OF_MIN, CURRENT_USER, UI_AS_OF, valid_as_of

_PROFILE_PHOTO = Path(__file__).resolve().parents[1] / "assets" / "profile.png"


def profile():
    photo = (html.Img(src="/assets/profile.png", alt="", className="sb-avatar")
             if _PROFILE_PHOTO.is_file() else
             html.Span(CURRENT_USER["name"][:1], className="sb-avatar", **{"aria-hidden": "true"}))
    return html.Div([
        photo,
        html.Div([
            html.Strong(CURRENT_USER["name"], className="sb-name"),
            html.Span(CURRENT_USER["title"], className="sb-title"),
            html.Span(CURRENT_USER["role"], className="sb-role"),
        ], className="sb-profile-text"),
    ], className="sb-profile")


def date_setting(as_of):
    return html.Div([
        html.Label("기준일", htmlFor="sb-date", className="sb-date-label"),
        dcc.DatePickerSingle(
            id="sb-date", date=as_of, min_date_allowed=AS_OF_MIN, max_date_allowed=AS_OF_MAX,
            initial_visible_month=as_of, display_format="YYYY-MM-DD", first_day_of_week=0,
            clearable=False, with_portal=True, className="sb-date",
        ),
        html.Button("오늘 날짜로", id="sb-date-reset", className="sb-date-reset"),
    ], className="sb-date-box")


def create_sidebar(active="main", as_of=UI_AS_OF):
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
            profile(),
            date_setting(as_of),
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


@callback(
    Output("store-as-of", "data"),
    Input("sb-date", "date"),
    Input("sb-date-reset", "n_clicks"),
    State("store-as-of", "data"),
    prevent_initial_call=True,
)
def set_as_of(date, reset, current):
    new = UI_AS_OF if ctx.triggered_id == "sb-date-reset" and reset else valid_as_of(date)
    if new == valid_as_of(current):
        raise PreventUpdate
    return new
