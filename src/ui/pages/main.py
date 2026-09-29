import calendar
from copy import deepcopy

import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import html, dcc, Input, Output, State, ALL, callback, ctx, no_update
from dash.exceptions import PreventUpdate

from src.ui.ai_data import f03_summary
from src.ui.config import UI_AS_OF
from src.ui.sample_data import (
    DEFAULT_SORT, F01_IS_NEW, F01_RISE, F02_IS_NEW, F02_STOCK, HISTORY, ISSUE_LABEL, KPIS,
    SORTS, STATUS_LABEL, item_by_key, ranked_items,
)

CAL_YEAR, CAL_MONTH = int(UI_AS_OF[:4]), int(UI_AS_OF[5:7])
TOP_N = 5
CHIPS_PER_DAY = 3
F03_MAX_LINKS = 3

# 차트 색: 00_tokens.css와 같은 값 (Plotly는 CSS 변수를 읽지 못함)
NAVY, YELLOW, ORANGE, DANGER = "#003566", "#ffc300", "#f77f00", "#d62839"
MUTED, GRID, INK = "#8a94a6", "#e3e7ed", "#1b2638"
FONT = "NanumSquare Neo, Malgun Gothic, sans-serif"

TOP5_CLOSED = ("mn-f02-slot mn-f02-slot-closed", "mn-middle-grid mn-middle-closed")
TOP5_OPEN = ("mn-f02-slot mn-f02-slot-open", "mn-middle-grid mn-middle-open")


def machine_label(machine):
    return f"M-{machine:03d}"


def item_title(item):
    parts = [machine_label(item["machine"])]
    if item.get("component"):
        parts.append(item["component"])
    parts.append(item["action"])
    return " · ".join(parts)


def d_day(date):
    if date[:7] != UI_AS_OF[:7]:
        return date[5:]
    days = int(date[8:10]) - int(UI_AS_OF[8:10])
    return "D-day" if days == 0 else (f"D-{days}" if days > 0 else f"D+{-days}")


def section_head(title, *extra, tag=None, icon=None, new=False):
    heading = [html.Span(icon, className="mn-head-icon", **{"aria-hidden": "true"}) if icon else None,
               html.Span(tag, className="mn-tag") if tag else None,
               title,
               html.Span("NEW", className="mn-new") if new else None]
    return html.Div([html.H2([part for part in heading if part is not None]), *extra],
                    className="mn-section-head")


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
    if dismissed_count:
        footer = html.Div([html.Span(f"처리해서 지운 항목 {dismissed_count}건"),
                           html.Button("모두 되돌리기", id="mn-top5-restore", className="mn-link-btn")],
                          className="mn-top5-foot")
    else:
        footer = html.Button(id="mn-top5-restore", className="mn-hidden")
    return [html.Div(cards, className="mn-timeline"), footer]


# ---------------- F01 / F02 / 과거 대응률 ----------------
def base_figure():
    figure = go.Figure()
    figure.update_layout(
        margin={"l": 8, "r": 16, "t": 16, "b": 8},
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font={"family": FONT, "size": 13, "color": INK},
        hoverlabel={"font": {"family": FONT}}, barcornerradius=6,
    )
    return figure


def f01_figure():
    rows = F01_RISE[:3]
    labels = [f"{machine_label(row['machine'])}<br><span style='font-size:11px'>{row['component']}</span>"
              for row in rows]
    rises = [row["after"] - row["before"] for row in rows]
    figure = base_figure()
    figure.add_trace(go.Bar(
        x=labels, y=rises, width=0.42, marker_color=[DANGER, ORANGE, YELLOW][:len(rows)],
        text=[f"+{rise}" for rise in rises], textposition="outside",
        textfont={"size": 16, "color": INK, "family": FONT},
        customdata=[[row["before"], row["after"]] for row in rows],
        hovertemplate="%{x}<br>지난주 %{customdata[0]} → 이번 주 %{customdata[1]}<extra></extra>",
    ))
    figure.update_yaxes(range=[0, max(rises) * 1.3], showgrid=True, gridcolor=GRID, zeroline=False,
                        tickfont={"color": MUTED}, title={"text": "상승(점)", "font": {"size": 12, "color": MUTED}})
    figure.update_xaxes(tickfont={"size": 14})
    figure.update_layout(showlegend=False)
    return figure


def f02_table(rows):
    head = html.Thead(html.Tr([html.Th(name) for name in ("순위", "부품", "재고", "위험 설비", "판정")]))
    body = html.Tbody([
        html.Tr([
            html.Td(str(rank)),
            html.Td([row["component"]] + ([html.Small(" 안전재고", className="mn-table-note")]
                                          if not row["adopted"] else [])),
            html.Td(f"{row['stock']}개"),
            html.Td(f"{row['risky']}대"),
            html.Td(html.Span(STATUS_LABEL[row["status"]], className=f"mn-status mn-status--{row['status']}")),
        ], className=f"mn-row--{row['status']}")
        for rank, row in enumerate(rows, 1)
    ])
    return html.Div(html.Table([head, body], className="mn-table"), className="mn-table-wrap")


def f01_full_table():
    head = html.Thead(html.Tr([html.Th(name) for name in ("순위", "설비", "부품", "지난주", "이번 주", "상승")]))
    body = html.Tbody([
        html.Tr([html.Td(str(rank)), html.Td(machine_label(row["machine"])), html.Td(row["component"]),
                 html.Td(row["before"]), html.Td(row["after"]), html.Td(f"+{row['after'] - row['before']}")])
        for rank, row in enumerate(F01_RISE, 1)
    ])
    return html.Div(html.Table([head, body], className="mn-table"), className="mn-table-wrap")


def history_figure(extra_handled=0):
    months = [row["month"] for row in HISTORY]
    handled = [row["handled"] for row in HISTORY]
    handled[-1] += extra_handled
    figure = base_figure()
    for name, values, color in (("예측 위험 설비", [row["risky"] for row in HISTORY], NAVY),
                                ("대응 완료(발주)", handled, YELLOW)):
        figure.add_trace(go.Scatter(
            x=months, y=values, name=name, mode="lines+markers",
            line={"color": color, "width": 3, "shape": "spline", "smoothing": .6},
            marker={"size": 10, "color": color, "line": {"color": "white", "width": 2}},
            hovertemplate=f"%{{x}}<br>{name} %{{y}}대 (누적)<extra></extra>",
        ))
    figure.update_layout(legend={"orientation": "h", "x": 1, "xanchor": "right", "y": 1.15,
                                 "font": {"size": 13, "color": INK}})
    figure.update_yaxes(rangemode="tozero", showgrid=True, gridcolor=GRID, zeroline=False,
                        tickfont={"color": MUTED}, title={"text": "누적 설비 수(대)", "font": {"size": 12, "color": MUTED}})
    figure.update_xaxes(tickfont={"size": 13})
    return figure


def history_rate(extra_handled=0):
    last = HISTORY[-1]
    return round(100 * min(last["handled"] + extra_handled, last["risky"]) / last["risky"])


def graph(graph_id, figure, height):
    return dcc.Graph(id=graph_id, figure=figure, config={"displayModeBar": False},
                     responsive=True, className="mn-graph", style={"height": height})


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
    # 요약이 여러 설비를 가리키면(targets) 설비마다 바로가기, 하나면 selected 하나
    targets = result.get("targets") or ([result["selected"]] if result.get("selected") else [])
    details += [dcc.Link(f"{machine_label(target['machineID'])} 상세 →",
                         href=f"/detail?machine={target['machineID']}", className="mn-f03-link")
                for target in targets[:F03_MAX_LINKS]]
    return html.Div(
        [html.Strong("AI 한 줄 요약", className="mn-f03-badge"),
         html.Span(result["text"], id="mn-summary", className="mn-f03-text"),
         html.Div(details, className="mn-f03-meta"),
         html.Button("오늘 할 일 TOP5 보기", id="mn-f03-top5", className="mn-f03-btn")],
        className="mn-f03", id="mn-f03",
    )


layout = html.Div(
    [
        # F03은 페이지를 열 때 저장된 예측 결과로 채운다.
        html.Div(className="mn-f03", id="mn-f03"),

        # 현재 상황 | 달력 | (토글) TOP5
        html.Div([
            html.Section([section_head("현재 상황"), make_kpis()],
                         className="mn-block mn-current-summary"),

            html.Section([
                section_head(
                    "To-Do 달력",
                    html.Div([html.Span([html.I(className="mn-legend-swatch mn-chip--part"), "부품 교체"]),
                              html.Span([html.I(className="mn-legend-swatch mn-chip--anomaly"), "이상 신호"]),
                              html.Span([html.I(className="mn-legend-rank"), "TOP5 순위"])],
                             className="mn-legend"),
                    html.Button("우선 확인 TOP5 보기", id="mn-show-top5", className="mn-toggle"),
                    tag="F04"),
                html.Div(id="mn-calendar-body", className="mn-calendar-wrap"),
                html.Small(f"기준일 {UI_AS_OF} · 항목을 누르면 상세 보기 · 처리 완료(삭제)를 선택할 수 있어요",
                           className="mn-hint"),
            ], className="mn-block mn-todo"),

            html.Section([
                section_head("우선 확인 설비 TOP5",
                             html.Button("✕", id="mn-close-top5", className="mn-close-btn",
                                         title="TOP5 닫기", **{"aria-label": "TOP5 닫기"})),
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
            ], id="mn-f02-slot", className=TOP5_CLOSED[0]),
        ], id="mn-middle", className=TOP5_CLOSED[1]),

        # F01 | F02 (첫 화면에서 여기까지 보이도록)
        html.Div([
            html.Section([
                section_head("확률 급상승 알림",
                             html.Button("전체보기 →", id="mn-f01-more", className="mn-more-btn"),
                             icon="⚡", new=F01_IS_NEW),
                html.P("지난주 대비 고장 위험도가 크게 오른 설비 TOP 3", className="mn-section-sub"),
                graph("mn-f01-graph", f01_figure(), "clamp(200px,22vh,250px)"),
            ], className="mn-block mn-insight"),
            html.Section([
                section_head("재고 × 위험 교차",
                             html.Button("전체보기 →", id="mn-f02-more", className="mn-more-btn"),
                             icon="📦", new=F02_IS_NEW),
                html.P("재고는 적은데 위험 설비가 많은 부품입니다", className="mn-section-sub"),
                f02_table(F02_STOCK[:3]),
            ], className="mn-block mn-insight"),
        ], className="mn-insights"),

        # 과거 대응률 (스크롤해서 보는 영역)
        html.Section([
            section_head("과거 대응률",
                         html.Div([html.Strong(f"{history_rate()}%", id="mn-history-rate"),
                                   html.Span("누적 대응률")], className="mn-insight-kpi"),
                         icon="📈"),
            html.P("예측 위험 설비 중 발주로 대응한 설비의 누적 추이 · 발주를 넣을 때마다 더해집니다",
                   className="mn-section-sub"),
            graph("mn-history-graph", history_figure(), "clamp(260px,32vh,360px)"),
        ], className="mn-block mn-history", id="mn-history"),
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

        # F01/F02 전체보기
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle(id="mn-more-title")),
            dbc.ModalBody(id="mn-more-body"),
        ], id="mn-more-modal", is_open=False, centered=True, className="mn-action-modal"),
    ],
    className="mn-page",
)


def create_main_layout():
    page = deepcopy(layout)
    page.children[0] = make_f03_panel()
    return page


@callback(
    Output("mn-f02-slot", "className"),
    Output("mn-middle", "className"),
    Output("mn-show-top5", "children"),
    Input("mn-show-top5", "n_clicks"),
    Input("mn-close-top5", "n_clicks"),
    Input("mn-f03-top5", "n_clicks"),
    State("mn-middle", "className"),
    prevent_initial_call=True,
)
def toggle_top5(_show, _close, _f03, middle_class):
    is_open = "mn-middle-open" in (middle_class or "")
    trigger = ctx.triggered_id
    opened = (False if trigger == "mn-close-top5" else
              True if trigger == "mn-f03-top5" else not is_open)
    slot, middle = TOP5_OPEN if opened else TOP5_CLOSED
    return slot, middle, "우선 확인 TOP5 닫기" if opened else "우선 확인 TOP5 보기"


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
    Output("mn-history-graph", "figure"),
    Output("mn-history-rate", "children"),
    Input("store-order-log", "data"),
)
def render_history(orders):
    count = len(orders or [])
    return history_figure(count), f"{history_rate(count)}%"


@callback(
    Output("mn-more-modal", "is_open"),
    Output("mn-more-title", "children"),
    Output("mn-more-body", "children"),
    Input("mn-f01-more", "n_clicks"),
    Input("mn-f02-more", "n_clicks"),
    prevent_initial_call=True,
)
def show_more(_f01, _f02):
    if ctx.triggered_id == "mn-f01-more":
        return True, "확률 급상승 알림 · 전체", f01_full_table()
    return True, "재고 × 위험 교차 · 전체", f02_table(F02_STOCK)


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
