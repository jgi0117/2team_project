import calendar
from copy import deepcopy

import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import html, dcc, Input, Output, State, ALL, callback, ctx, no_update
from dash.exceptions import PreventUpdate

from src.ui.ai_data import f03_summary
from src.ui.config import UI_AS_OF
from src.ui.sample_data import (
    DEFAULT_SORT, F01_RISE, F02_STOCK, F04_RESPONSE, ISSUE_LABEL, KPIS, SORTS,
    item_by_key, ranked_items,
)

CAL_YEAR, CAL_MONTH = int(UI_AS_OF[:4]), int(UI_AS_OF[5:7])
TOP_N = 5
CHIPS_PER_DAY = 3

# 차트 색: 00_tokens.css와 같은 값 (Plotly는 CSS 변수를 읽지 못함)
NAVY, NAVY_DARK, YELLOW = "#003566", "#001d3d", "#ffc300"
MUTED, GRID, INK = "#8a94a6", "#e3e7ed", "#1b2638"
DANGER = "#d62839"
FONT = "NanumSquare Neo, Malgun Gothic, sans-serif"


def machine_label(machine):
    return f"M-{machine:03d}"


def item_title(item):
    parts = [machine_label(item["machine"])]
    if item.get("component"):
        parts.append(item["component"])
    parts.append(item["action"])
    return " · ".join(parts)


def d_day(date):
    days = (int(date[8:10]) - int(UI_AS_OF[8:10])) if date[:7] == UI_AS_OF[:7] else None
    if days is None:
        return date[5:]
    return "D-day" if days == 0 else (f"D-{days}" if days > 0 else f"D+{-days}")


# ---------------- 현재 상황 ----------------
def make_kpis():
    tiles = []
    for title, icon, value, unit, change, state in KPIS:
        delta = []
        if change:
            arrow = "▲" if change.startswith("+") else ("▼" if change.startswith("-") else "–")
            delta = html.Span(f"지난주 대비 {arrow} {change.lstrip('+-')}{unit}",
                              className="mn-kpi-delta")
        tiles.append(html.Div(
            [html.Div([html.Span(icon, className="mn-kpi-icon", **{"aria-hidden": "true"}),
                       html.Span(title, className="mn-kpi-title")], className="mn-kpi-head"),
             html.Div([html.Strong(value), html.Span(unit)], className="mn-kpi-value"),
             delta],
            className=f"mn-kpi mn-kpi--{state}",
        ))
    return html.Div(tiles, className="mn-kpis")


# ---------------- F04 To-Do 달력 ----------------
def cal_chip(item, rank):
    top = rank is not None
    return html.Button(
        [html.Span(str(rank) if top else "", className="mn-chip-rank"),
         html.Span([html.B(machine_label(item["machine"])),
                    html.Span(" · ".join(filter(None, [item.get("component"), item["action"]])))],
                   className="mn-chip-text")],
        id={"type": "mn-cal-item", "key": item["key"]},
        className=f"mn-chip mn-chip--{item['issue']}" + (" is-top" if top else " is-rest"),
        title=f"{item_title(item)} — {item['note']}",
    )


def make_calendar(items, ranks):
    by_date = {}
    for item in items:
        by_date.setdefault(item["date"], []).append(item)
    for day_items in by_date.values():
        day_items.sort(key=lambda item: ranks.get(item["key"], 99))

    first_weekday, days = calendar.monthrange(CAL_YEAR, CAL_MONTH)
    # monthrange는 월요일=0 → 일요일 시작 달력의 앞쪽 빈 칸 수
    cells = [html.Div(className="mn-day mn-day--blank")
             for _ in range((first_weekday + 1) % 7)]
    for day in range(1, days + 1):
        date = f"{CAL_YEAR}-{CAL_MONTH:02d}-{day:02d}"
        day_items = by_date.get(date, [])
        chips = [cal_chip(item, ranks.get(item["key"])) for item in day_items[:CHIPS_PER_DAY]]
        if len(day_items) > CHIPS_PER_DAY:
            chips.append(html.Span(f"+{len(day_items) - CHIPS_PER_DAY}건 더", className="mn-chip-more"))
        state = ("mn-day--today" if date == UI_AS_OF else
                 "mn-day--past" if date < UI_AS_OF else "")
        cells.append(html.Div(
            [html.Span(str(day), className="mn-day-num"), html.Div(chips, className="mn-day-items")],
            className=f"mn-day {state}".strip(),
        ))
    week = [html.Div(name, className="mn-week-day" + (" is-weekend" if name in "일토" else ""))
            for name in "일월화수목금토"]
    return [html.Div(week, className="mn-week"), html.Div(cells, className="mn-calendar")]


# ---------------- 우선 확인 설비 TOP5 ----------------
def metric(label, value, extra=""):
    return html.Div([html.Span(label), html.Strong(value)], className=f"mn-metric {extra}".strip())


def top5_card(item, rank):
    head = html.Div([
        html.Span(str(rank), className="mn-card-rank"),
        html.Strong(machine_label(item["machine"]), className="mn-card-machine"),
        html.Span(ISSUE_LABEL[item["issue"]] + (f" · {item['component']}" if item.get("component") else ""),
                  className=f"mn-issue mn-issue--{item['issue']}"),
        html.Span(f"{item['date'][5:].replace('-', '/')} {item['action']} · {d_day(item['date'])}",
                  className="mn-card-date"),
    ], className="mn-card-head")
    body = [head, html.P(item["note"], className="mn-card-note")]
    if item["issue"] == "part":
        body.append(html.Div([
            html.Div([
                html.Span("고장 위험도"), html.Strong(f"{item['risk']}"),
                html.Div(html.Div(className="mn-risk-fill", style={"width": f"{item['risk']}%"}),
                         className="mn-risk-bar"),
            ], className="mn-metric mn-risk", title="다른 설비와 비교한 상대 점수입니다 (확률 아님)"),
            metric("발주 마감", f"{item['deadline'][5:].replace('-', '/')} ({d_day(item['deadline'])})",
                   "is-alert" if item["slack"] <= 3 else ""),
            metric("지연 시 손실", f"{item['loss']:,}만원"),
            metric("재고", f"{item['stock']}개", "is-alert" if item["stock"] == 0 else ""),
        ], className="mn-card-metrics"))
    return html.Button(body, id={"type": "mn-top5-card", "key": item["key"]},
                       className=f"mn-card mn-card--{item['issue']}" + (" is-first" if rank == 1 else ""))


def make_top5(items, dismissed_count):
    if not items:
        cards = [html.Div("남은 우선 확인 항목이 없습니다", className="mn-empty")]
    else:
        cards = [html.Div([html.Span(className="mn-timeline-dot"), top5_card(item, rank)],
                          className="mn-timeline-row")
                 for rank, item in enumerate(items, 1)]
    footer = []
    if dismissed_count:
        footer = html.Div([html.Span(f"처리해서 지운 항목 {dismissed_count}건"),
                           html.Button("모두 되돌리기", id="mn-top5-restore", className="mn-link-btn")],
                          className="mn-top5-foot")
    else:
        footer = html.Button(id="mn-top5-restore", className="mn-hidden")
    return [html.Div(cards, className="mn-timeline"), footer]


# ---------------- 하단 차트 ----------------
def base_figure():
    figure = go.Figure()
    figure.update_layout(
        margin={"l": 8, "r": 16, "t": 8, "b": 8},
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font={"family": FONT, "size": 13, "color": INK},
        hoverlabel={"font": {"family": FONT}}, barcornerradius=4,
        legend={"orientation": "h", "x": 0, "y": 1.12, "font": {"size": 12, "color": MUTED}},
    )
    return figure


def f01_figure():
    rows = list(reversed(F01_RISE))
    labels = [row["label"] for row in rows]
    figure = base_figure()
    for row in rows:
        figure.add_trace(go.Scatter(x=[row["before"], row["after"]], y=[row["label"]] * 2,
                                    mode="lines", line={"color": GRID, "width": 6},
                                    hoverinfo="skip", showlegend=False))
    figure.add_trace(go.Scatter(
        x=[row["before"] for row in rows], y=labels, mode="markers", name="지난주",
        marker={"size": 12, "color": MUTED, "line": {"color": "white", "width": 2}},
        hovertemplate="%{y}<br>지난주 %{x}<extra></extra>"))
    figure.add_trace(go.Scatter(
        x=[row["after"] for row in rows], y=labels, mode="markers+text", name="이번 주",
        marker={"size": 14, "color": NAVY, "line": {"color": "white", "width": 2}},
        text=[f"+{row['after'] - row['before']}" for row in rows], textposition="middle right",
        textfont={"color": INK, "size": 13},
        hovertemplate="%{y}<br>이번 주 %{x}<extra></extra>"))
    figure.update_xaxes(range=[0, 108], showgrid=True, gridcolor=GRID, zeroline=False,
                        tickfont={"color": MUTED}, title=None)
    figure.update_yaxes(showgrid=False, tickfont={"size": 13})
    return figure


def f02_figure():
    comps = [row["component"] + ("" if row["adopted"] else "<br><sub>안전재고</sub>") for row in F02_STOCK]
    figure = base_figure()
    figure.add_trace(go.Bar(x=comps, y=[row["need"] for row in F02_STOCK], name="필요 예상",
                            marker_color=NAVY, width=0.3, offset=-0.32,
                            text=[row["need"] for row in F02_STOCK], textposition="outside",
                            textfont={"color": INK},
                            hovertemplate="%{x}<br>필요 예상 %{y}개<extra></extra>"))
    figure.add_trace(go.Bar(x=comps, y=[row["stock"] for row in F02_STOCK], name="보유 재고",
                            marker_color=YELLOW, width=0.3, offset=0.02,
                            text=[row["stock"] for row in F02_STOCK], textposition="outside",
                            textfont={"color": INK},
                            hovertemplate="%{x}<br>보유 재고 %{y}개<extra></extra>"))
    for comp, row in zip(comps, F02_STOCK):
        short = row["need"] - row["stock"]
        if row["adopted"] and short > 0:
            figure.add_annotation(x=comp, y=max(row["need"], row["stock"]) + 1.6,
                                  text=f"⚠ {short}개 부족", showarrow=False,
                                  font={"color": DANGER, "size": 12})
    top = max(max(row["need"], row["stock"]) for row in F02_STOCK)
    figure.update_yaxes(range=[0, top + 2.6], showgrid=True, gridcolor=GRID, zeroline=False,
                        tickfont={"color": MUTED}, title=None)
    figure.update_xaxes(tickfont={"size": 13})
    figure.update_layout(bargap=0.3)
    return figure


def f04_figure():
    weeks = [row["week"] for row in F04_RESPONSE]
    figure = base_figure()
    figure.add_trace(go.Bar(x=weeks, y=[row["done"] for row in F04_RESPONSE], name="대응 완료",
                            marker_color=NAVY, width=0.5,
                            hovertemplate="%{x} 주<br>대응 완료 %{y}대<extra></extra>"))
    figure.add_trace(go.Bar(x=weeks, y=[row["open"] for row in F04_RESPONSE], name="미대응",
                            marker_color=YELLOW, width=0.5,
                            hovertemplate="%{x} 주<br>미대응 %{y}대<extra></extra>"))
    figure.update_layout(barmode="stack", legend_traceorder="normal")
    figure.update_traces(marker_line={"color": "white", "width": 2})
    figure.update_yaxes(showgrid=True, gridcolor=GRID, zeroline=False, tickfont={"color": MUTED}, title=None)
    figure.update_xaxes(type="category", tickfont={"color": MUTED})
    return figure


def response_rate():
    last = F04_RESPONSE[-1]
    return round(100 * last["done"] / (last["done"] + last["open"]))


def insight(title, subtitle, figure, graph_id, extra=None, section_id=None):
    head = [html.Div([html.H3(title), html.Span(subtitle)], className="mn-insight-title")]
    if extra:
        head.append(extra)
    return html.Section(
        [html.Div(head, className="mn-insight-head"),
         dcc.Graph(id=graph_id, figure=figure, config={"displayModeBar": False},
                   responsive=True, className="mn-graph",
                   style={"height": "clamp(210px,23vh,270px)"})],
        className="mn-insight", **({"id": section_id} if section_id else {}),
    )


# ---------------- F03 ----------------
def make_f03_panel():
    try:
        result = f03_summary(UI_AS_OF)
    except (OSError, ValueError, KeyError, IndexError):
        result = {"text": "고장 예측 결과를 불러오지 못했습니다.", "selected": None,
                  "prediction_as_of": None, "horizon_days": None}
    observed = result.get("prediction_as_of")
    horizon = result.get("horizon_days")
    details = []
    if observed:
        details.append(html.Span(f"예측 기준 {observed[:10]}"))
    if horizon:
        details.append(html.Span(f"향후 {horizon}일 고장 위험"))
    selected = result.get("selected")
    if selected:
        details.append(dcc.Link(
            f"설비 M-{selected['machineID']:03d} 상세 보기 →",
            href=f"/detail?machine={selected['machineID']}",
            className="mn-f03-link",
        ))
    return html.Div(
        [html.Strong("AI 한 줄 요약", className="mn-f03-badge"),
         html.Span(result["text"], id="mn-summary", className="mn-f03-text"),
         html.Div(details, className="mn-f03-meta")],
        className="mn-f03", id="mn-f03",
    )


def section_head(title, *extra, tag=None):
    return html.Div(
        [html.H2([html.Span(tag, className="mn-tag"), title] if tag else title), *extra],
        className="mn-section-head",
    )


layout = html.Div(
    [
        # F03은 페이지를 열 때 저장된 예측 결과로 채운다.
        html.Div(className="mn-f03", id="mn-f03"),

        html.Section([section_head("현재 상황", html.Span(f"기준일 {UI_AS_OF}", className="mn-asof")),
                      make_kpis()],
                     className="mn-block mn-current-summary"),

        html.Div([
            html.Section([
                section_head(
                    "To-Do 달력",
                    html.Div([html.Span([html.I(className="mn-legend-swatch mn-chip--part"), "부품 교체"]),
                              html.Span([html.I(className="mn-legend-swatch mn-chip--anomaly"), "이상 신호"]),
                              html.Span([html.I(className="mn-legend-rank"), "TOP5 순위"])],
                             className="mn-legend"),
                    tag="F04"),
                html.Div(id="mn-calendar-body", className="mn-calendar-wrap"),
                html.Small("항목을 누르면 상세 보기 · 처리 완료(삭제)를 선택할 수 있어요", className="mn-hint"),
            ], className="mn-block mn-todo"),

            html.Section([
                section_head("우선 확인 설비 TOP5"),
                html.Div([
                    html.Label("정렬 기준", htmlFor="mn-top5-sort", className="mn-sort-label"),
                    html.Div(dcc.Dropdown(
                        id="mn-top5-sort",
                        options=[{"label": label, "value": value} for value, (label, _) in SORTS.items()],
                        value=DEFAULT_SORT, clearable=False, searchable=False,
                        style={"width": "100%"},
                    ), className="mn-sort"),
                ], className="mn-sort-row"),
                html.Div(id="mn-top5-panel"),
            ], className="mn-block mn-f02"),
        ], className="mn-work"),

        html.Div([
            insight("확률 급상승 알림", "지난주 대비 위험도가 크게 오른 설비 TOP3",
                    f01_figure(), "mn-f01-graph"),
            insight("재고 × 위험 교차", "부품별 필요 예상 수량과 보유 재고",
                    f02_figure(), "mn-f02-graph"),
            insight("위험 대응률", "주차별 위험 설비 대응 현황",
                    f04_figure(), "mn-f04-graph",
                    extra=html.Div([html.Strong(f"{response_rate()}%"), html.Span("이번 주")],
                                   className="mn-insight-kpi"),
                    section_id="mn-history"),
        ], className="mn-insights"),
        html.Small("달력·TOP5·하단 그래프는 UI 확인용 예시 데이터입니다.", className="mn-sample-note"),

        # 항목 클릭 시 뜨는 작은 선택 창
        dcc.Store(id="mn-action-key"),
        dbc.Modal([
            dbc.ModalBody([
                html.Div(id="mn-action-body"),
                html.Div([
                    dcc.Link("상세 보기", id="mn-action-detail", href="/detail", className="mn-btn mn-btn--primary"),
                    html.Button("처리 완료 · 삭제", id="mn-action-delete", className="mn-btn mn-btn--danger"),
                    html.Button("닫기", id="mn-action-cancel", className="mn-btn"),
                ], className="mn-action-btns"),
            ]),
        ], id="mn-action-modal", is_open=False, centered=True, size="sm", className="mn-action-modal"),
    ],
    className="mn-page",
)


def create_main_layout():
    page = deepcopy(layout)
    page.children[0] = make_f03_panel()
    return page


@callback(
    Output("mn-calendar-body", "children"),
    Output("mn-top5-panel", "children"),
    Input("store-todo-dismissed", "data"),
    Input("mn-top5-sort", "value"),
)
def render_todo(dismissed, sort):
    items = ranked_items(dismissed, sort)
    top = items[:TOP_N]
    ranks = {item["key"]: rank for rank, item in enumerate(top, 1)}
    return make_calendar(items, ranks), make_top5(top, len(dismissed or []))


@callback(
    Output("mn-action-modal", "is_open"),
    Output("mn-action-key", "data"),
    Output("mn-action-body", "children"),
    Output("mn-action-detail", "href"),
    Input({"type": "mn-cal-item", "key": ALL}, "n_clicks"),
    Input({"type": "mn-top5-card", "key": ALL}, "n_clicks"),
    Input("mn-action-cancel", "n_clicks"),
    Input("mn-action-delete", "n_clicks"),
    prevent_initial_call=True,
)
def open_action(_cal, _cards, _cancel, _delete):
    trigger = ctx.triggered_id
    if trigger in ("mn-action-cancel", "mn-action-delete"):
        return False, None, no_update, no_update
    # 항목이 다시 그려질 때도 호출되므로 실제 클릭(n_clicks > 0)만 처리
    if not isinstance(trigger, dict) or not ctx.triggered[0]["value"]:
        raise PreventUpdate
    item = item_by_key(trigger["key"])
    if item is None:
        raise PreventUpdate
    body = [html.Strong(item_title(item), className="mn-action-title"),
            html.Span(f"{ISSUE_LABEL[item['issue']]} · {item['date']}", className="mn-action-sub"),
            html.P(item["note"], className="mn-action-note")]
    return True, item["key"], body, f"/detail?machine={item['machine']}"


@callback(
    Output("store-todo-dismissed", "data", allow_duplicate=True),
    Input("mn-action-delete", "n_clicks"),
    Input("mn-top5-restore", "n_clicks"),
    State("mn-action-key", "data"),
    State("store-todo-dismissed", "data"),
    prevent_initial_call=True,
)
def update_dismissed(_delete, restore, key, dismissed):
    if ctx.triggered_id == "mn-top5-restore":
        if not restore:
            raise PreventUpdate
        return []
    if not key:
        raise PreventUpdate
    return list(dict.fromkeys([*(dismissed or []), key]))
