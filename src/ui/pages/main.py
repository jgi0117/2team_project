import calendar

import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import html, dcc, Input, Output, State, ALL, callback, ctx, no_update
from dash.exceptions import PreventUpdate

from src.ui.ai_data import f03_summary
from src.ui.config import UI_AS_OF, valid_as_of
from src.ui.sample_data import (
    DEFAULT_SORT, F01_RISE, F02_STOCK, ISSUE_LABEL, KPIS, SORTS, STATUS_LABEL,
    available_months, history, item_by_key, kpi_detail, ranked_items,
)

TOP_N = 5
CHIPS_PER_DAY = 3
F03_MAX_LINKS = 3

# 차트 색: 00_tokens.css와 같은 값 (Plotly는 CSS 변수를 읽지 못함)
NAVY, NAVY_DARK, YELLOW = "#003566", "#001d3d", "#ffc300"
NAVY_SOFT, MUTED, GRID, INK = "#9fb3cc", "#8a94a6", "#e3e7ed", "#0f1a2b"
FONT = "NanumSquare Neo, Malgun Gothic, sans-serif"
TARGET_RATE = 80  # 적시 대응률 목표선 (%)

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


def d_day(date, as_of):
    from datetime import date as _date
    days = (_date.fromisoformat(date) - _date.fromisoformat(as_of)).days
    return "D-day" if days == 0 else (f"D-{days}" if days > 0 else f"D+{-days}")


def section_head(title, *extra):
    return html.Div([html.H2(title), *extra], className="mn-section-head")


def status_badge(status):
    return html.Span(STATUS_LABEL[status], className=f"mn-status mn-status--{status}")


# ---------------- 현재 상황 ----------------
def make_kpis():
    tiles = []
    for key, title, icon, value, unit, change, state in KPIS:
        delta = []
        if change:
            arrow = "▲" if change.startswith("+") else ("▼" if change.startswith("-") else "–")
            delta = html.Span(f"지난주 대비 {arrow} {change.lstrip('+-')}{unit}",
                              className="mn-kpi-delta")
        tiles.append(html.Button(
            [html.Div([html.Span(icon, className="mn-kpi-icon", **{"aria-hidden": "true"}),
                       html.Span(title, className="mn-kpi-title"),
                       html.Span("›", className="mn-kpi-more", **{"aria-hidden": "true"})],
                      className="mn-kpi-head"),
             html.Div([html.Strong(value), html.Span(unit)], className="mn-kpi-value"),
             delta],
            id={"type": "mn-kpi", "key": key},
            className=f"mn-kpi mn-kpi--{state}", title=f"{title} 상세 보기",
        ))
    return html.Div(tiles, className="mn-kpis")


def kpi_table(detail):
    def cell(column, value):
        if column == "설비":
            return html.Td(dcc.Link(f"{machine_label(value)} →", href=f"/detail?machine={value}",
                                    className="mn-row-link"))
        if column == "판정":
            return html.Td(status_badge(value))
        return html.Td(value)

    return html.Div([
        html.P(detail["desc"], className="mn-modal-desc"),
        html.Div(html.Table([
            html.Thead(html.Tr([html.Th(column) for column in detail["columns"]])),
            html.Tbody([html.Tr([cell(column, value) for column, value in zip(detail["columns"], row)])
                        for row in detail["rows"]]),
        ], className="mn-table"), className="mn-table-wrap"),
        html.Small("설비 번호를 누르면 설비 상세 화면으로 이동합니다.", className="mn-modal-hint"),
    ])


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


def make_calendar(items, ranks, as_of):
    year, month = int(as_of[:4]), int(as_of[5:7])
    by_date = {}
    for item in items:
        by_date.setdefault(item["date"], []).append(item)
    for day_items in by_date.values():
        day_items.sort(key=lambda item: ranks.get(item["key"], 99))

    first_weekday, days = calendar.monthrange(year, month)
    # monthrange는 월요일=0 → 일요일 시작 달력의 앞쪽 빈 칸 수
    cells = [html.Div(className="mn-day mn-day--blank")
             for _ in range((first_weekday + 1) % 7)]
    for day in range(1, days + 1):
        date = f"{year}-{month:02d}-{day:02d}"
        day_items = by_date.get(date, [])
        chips = [cal_chip(item, ranks.get(item["key"])) for item in day_items[:CHIPS_PER_DAY]]
        if len(day_items) > CHIPS_PER_DAY:
            chips.append(html.Span(f"+{len(day_items) - CHIPS_PER_DAY}건 더", className="mn-chip-more"))
        state = ("mn-day--today" if date == as_of else
                 "mn-day--past" if date < as_of else "")
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


def top5_card(item, rank, as_of):
    head = html.Div([
        html.Span(str(rank), className="mn-card-rank"),
        html.Strong(machine_label(item["machine"]), className="mn-card-machine"),
        html.Span(ISSUE_LABEL[item["issue"]] + (f" · {item['component']}" if item.get("component") else ""),
                  className=f"mn-issue mn-issue--{item['issue']}"),
        html.Span(f"{item['date'][5:].replace('-', '/')} {item['action']} · {d_day(item['date'], as_of)}",
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
            metric("발주 마감", f"{item['deadline'][5:].replace('-', '/')} ({d_day(item['deadline'], as_of)})",
                   "is-alert" if item["slack"] <= 3 else ""),
            metric("지연 시 손실", f"{item['loss']:,}만원"),
            metric("재고", f"{item['stock']}개", "is-alert" if item["stock"] == 0 else ""),
        ], className="mn-card-metrics"))
    return html.Button(body, id={"type": "mn-top5-card", "key": item["key"]},
                       className=f"mn-card mn-card--{item['issue']}" + (" is-first" if rank == 1 else ""))


def make_top5(items, dismissed_count, as_of):
    if not items:
        cards = [html.Div("남은 우선 확인 항목이 없습니다", className="mn-empty")]
    else:
        cards = [html.Div([html.Span(className="mn-timeline-dot"), top5_card(item, rank, as_of)],
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
        hoverlabel={"font": {"family": FONT}}, barcornerradius=6, showlegend=False,
    )
    return figure


def f01_figure(rows):
    """상승폭이 큰 순서대로 받은 행을 막대로. 1위만 노랑으로 강조."""
    labels = [f"{machine_label(row['machine'])}<br><span style='font-size:11px;color:{MUTED}'>"
              f"{row['component']}</span>" for row in rows]
    rises = [row["after"] - row["before"] for row in rows]
    figure = base_figure()
    figure.add_trace(go.Bar(
        x=labels, y=rises, width=0.36, marker_color=[YELLOW] + [NAVY] * (len(rows) - 1),
        text=[f"+{rise}" for rise in rises], textposition="outside", cliponaxis=False,
        textfont={"size": 15, "color": INK, "family": FONT},
        customdata=[[row["before"], row["after"]] for row in rows],
        hovertemplate="%{x}<br>지난주 %{customdata[0]} → 이번 주 %{customdata[1]}<extra></extra>",
    ))
    figure.update_yaxes(range=[0, max(rises or [1]) * 1.3], showgrid=True, gridcolor=GRID, zeroline=False,
                        tickfont={"color": MUTED}, title={"text": "상승(점)", "font": {"size": 12, "color": MUTED}})
    figure.update_xaxes(tickfont={"size": 14})
    return figure


def f02_table(rows):
    head = html.Thead(html.Tr([html.Th(name) for name in ("순위", "부품", "재고", "위험 설비", "판정")]))
    body = html.Tbody([
        html.Tr([
            html.Td(str(rank)),
            html.Td([row["component"]] + ([html.Small(" 안전재고", className="mn-table-note")]
                                          if not row["adopted"] else [])),
            html.Td(f"{row['stock']}개", className="is-alert" if row["stock"] == 0 else ""),
            html.Td(f"{row['risky']}대"),
            html.Td(status_badge(row["status"])),
        ], className=f"mn-row--{row['status']}")
        for rank, row in enumerate(rows, 1)
    ])
    return html.Div(html.Table([head, body], className="mn-table"), className="mn-table-wrap")


def f01_full_table():
    head = html.Thead(html.Tr([html.Th(name) for name in ("순위", "설비", "부품", "지난주", "이번 주", "상승")]))
    body = html.Tbody([
        html.Tr([html.Td(str(rank)),
                 html.Td(dcc.Link(f"{machine_label(row['machine'])} →", href=f"/detail?machine={row['machine']}",
                                  className="mn-row-link")),
                 html.Td(row["component"]), html.Td(row["before"]), html.Td(row["after"]),
                 html.Td(f"+{row['after'] - row['before']}")])
        for rank, row in enumerate(F01_RISE, 1)
    ])
    return html.Div(html.Table([head, body], className="mn-table"), className="mn-table-wrap")


def rate_figure(rows):
    """월별 적시 대응률(%). 진행 중인 달은 점선과 속이 빈 점으로 구분."""
    months = [row["month"] for row in rows]
    rates = [round(100 * row["on_time"] / row["due"]) if row["due"] else None for row in rows]
    live = bool(rows) and rows[-1]["current"]
    done = len(rows) - 1 if live else len(rows)
    hover = "%{x}<br>마감 %{customdata[1]}건 중 제때 발주 %{customdata[0]}건 · %{y}%<extra></extra>"
    figure = base_figure()
    figure.add_hline(y=TARGET_RATE, line={"color": NAVY_SOFT, "width": 1, "dash": "dot"},
                     annotation={"text": f"목표 {TARGET_RATE}%", "font": {"size": 11, "color": MUTED}},
                     annotation_position="top left")
    figure.add_trace(go.Scatter(
        x=months[:done], y=rates[:done], mode="lines+markers+text", name="적시 대응률",
        line={"color": NAVY, "width": 2}, text=[f"{rate}%" for rate in rates[:done]],
        textposition="top center", textfont={"size": 12, "color": INK},
        marker={"size": 9, "color": NAVY, "line": {"color": "white", "width": 2}},
        customdata=[[row["on_time"], row["due"]] for row in rows[:done]], hovertemplate=hover,
    ))
    if live:
        tail = slice(max(done - 1, 0), len(rows))
        figure.add_trace(go.Scatter(
            x=months[tail], y=rates[tail], mode="lines+markers+text", name="진행 중",
            line={"color": NAVY, "width": 2, "dash": "dot"},
            text=[""] * (len(months[tail]) - 1) + [f"{rates[-1]}% (진행 중)"], textposition="top center",
            textfont={"size": 12, "color": INK},
            marker={"size": [0] * (len(months[tail]) - 1) + [11], "color": "white",
                    "line": {"color": YELLOW, "width": 3}},
            customdata=[[row["on_time"], row["due"]] for row in rows[tail]], hovertemplate=hover,
        ))
    figure.update_yaxes(range=[0, 108], ticksuffix="%", showgrid=True, gridcolor=GRID, zeroline=False,
                        tickfont={"color": MUTED})
    figure.update_xaxes(type="category", tickfont={"size": 13})
    return figure


def saving_figure(rows):
    """월별 절감액(만원). 이번 달은 노랑(진행 중)."""
    figure = base_figure()
    figure.add_trace(go.Bar(
        x=[row["month"] for row in rows], y=[row["saved"] for row in rows], width=0.45,
        marker_color=[YELLOW if row["current"] else NAVY for row in rows],
        text=[f"{row['saved']:,}" for row in rows], textposition="outside", cliponaxis=False,
        textfont={"size": 12, "color": INK},
        hovertemplate="%{x}<br>절감액 %{y:,}만원<extra></extra>",
    ))
    figure.update_yaxes(range=[0, max([row["saved"] for row in rows] or [1]) * 1.25], showgrid=True, gridcolor=GRID,
                        zeroline=False, tickfont={"color": MUTED},
                        title={"text": "만원", "font": {"size": 12, "color": MUTED}})
    figure.update_xaxes(type="category", tickfont={"size": 13})
    return figure


def history_summary(rows):
    due = sum(row["due"] for row in rows)
    rate = round(100 * sum(row["on_time"] for row in rows) / due) if due else 0
    saved = sum(row["saved"] for row in rows)
    period = f"{rows[0]['key']} ~ {rows[-1]['key']}" if rows else ""
    return [
        html.Div([html.Span(f"적시 대응률 · {period}"), html.Strong(f"{rate}%")], className="mn-hist-kpi"),
        html.Div([html.Span(f"누적 절감액 · {period}"), html.Strong(f"{saved:,}만원")],
                 className="mn-hist-kpi is-accent"),
    ]


HIST_RANGES = [("3", "최근 3개월"), ("6", "최근 6개월"), ("all", "전체"), ("custom", "직접 설정")]


def hist_bounds(as_of, choice, start, end):
    months = available_months(as_of)
    if choice == "custom":
        return start, end
    if choice == "all":
        return months[0], months[-1]
    return months[max(0, len(months) - int(choice or 6))], months[-1]


def graph(graph_id, figure, height):
    return dcc.Graph(id=graph_id, figure=figure, config={"displayModeBar": False},
                     responsive=True, className="mn-graph", style={"height": height})


# ---------------- F03 ----------------
def make_f03_panel(as_of=UI_AS_OF):
    try:
        result = f03_summary(as_of)
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
         html.Div(details, className="mn-f03-meta")],
        className="mn-f03", id="mn-f03",
    )


def build_layout(as_of, f03=None):
    months = available_months(as_of)
    month_options = [{"label": f"{m[:4]}년 {int(m[5:])}월", "value": m} for m in months]
    return html.Div(
        [
            # AI 한 줄 요약은 페이지를 열 때 저장된 예측 결과로 채운다.
            f03 if f03 is not None else html.Div(className="mn-f03", id="mn-f03"),

            # 현재 상황 | [달력 | (토글) TOP5] — 달력 쪽이 화면의 중심(흰 판)
            html.Div([
                html.Section([section_head("현재 상황", html.Span("카드를 누르면 상세", className="mn-head-hint")),
                              make_kpis()],
                             className="mn-block mn-current-summary"),

                html.Div([
                    html.Div([
                        html.H2(["To-Do 달력", html.Span(f"{int(as_of[:4])}년 {int(as_of[5:7])}월",
                                                        className="mn-cal-month")]),
                        html.Div([html.Span([html.I(className="mn-legend-swatch mn-chip--part"), "부품 교체"]),
                                  html.Span([html.I(className="mn-legend-swatch mn-chip--anomaly"), "이상 신호"]),
                                  html.Span([html.I(className="mn-legend-rank"), "우선순위"])],
                                 className="mn-legend"),
                        html.Button("우선 확인 TOP5 보기", id="mn-show-top5", className="mn-toggle"),
                    ], className="mn-hero-head"),
                    html.Div([
                        html.Section([
                            html.Div(id="mn-calendar-body", className="mn-calendar-wrap"),
                            html.Small(f"기준일 {as_of} · 항목을 누르면 상세 보기 · 처리 완료(삭제)를 선택할 수 있어요",
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
                    ], className="mn-hero-body"),
                ], className="mn-hero"),
            ], id="mn-middle", className=TOP5_CLOSED[1]),

            # 확률 급상승 | 재고 × 위험 (첫 화면에서 여기까지)
            html.Div([
                html.Section([
                    section_head("확률 급상승 알림",
                                 html.Button("전체보기 →", id="mn-f01-more", className="mn-more-btn")),
                    html.P("지난주 대비 고장 위험도가 크게 오른 설비 TOP 3", className="mn-section-sub"),
                    graph("mn-f01-graph", f01_figure(F01_RISE[:3]), "clamp(190px,20vh,230px)"),
                ], className="mn-block mn-insight"),
                html.Section([
                    section_head("재고 × 위험 교차"),
                    html.P("재고는 적은데 위험 설비가 많은 부품 순서입니다", className="mn-section-sub"),
                    f02_table(F02_STOCK),
                ], className="mn-block mn-insight"),
            ], className="mn-insights mn-band"),

            # 과거 대응률 (스크롤해서 보는 영역)
            html.Section([
                section_head("과거 대응률",
                             html.Div([
                                 dcc.RadioItems(id="mn-hist-range",
                                                options=[{"label": label, "value": value}
                                                         for value, label in HIST_RANGES],
                                                value="6", className="mn-seg", inline=True),
                                 html.Div([
                                     dcc.Dropdown(id="mn-hist-start", options=month_options,
                                                  value=months[max(0, len(months) - 6)], clearable=False,
                                                  searchable=False, className="mn-month-select"),
                                     html.Span("~"),
                                     dcc.Dropdown(id="mn-hist-end", options=month_options, value=months[-1],
                                                  clearable=False, searchable=False, className="mn-month-select"),
                                 ], id="mn-hist-custom", className="mn-hist-custom is-hidden"),
                             ], className="mn-hist-controls")),
                html.Div(history_summary(history(as_of)), id="mn-history-rate", className="mn-hist-kpis"),
                html.Div([
                    html.Div([html.H3("월별 적시 대응률"),
                              html.P("그 달에 발주 마감이 온 위험 건 중 마감 전에 발주한 비율 "
                                     "(마감월 기준이라 다음 달에 처리해도 원래 달의 성적으로 계산)",
                                     className="mn-chart-note"),
                              graph("mn-history-graph", rate_figure(history(as_of)), "clamp(240px,28vh,320px)")],
                             className="mn-hist-chart"),
                    html.Div([html.H3("월별 절감액"),
                              html.P("절감액 = 고장 후 대응 비용(부품가 + 긴급 할증 + 긴급 정비 인건비 + 설비 정지 손실) "
                                     "− 계획 대응 비용(부품가 + 발주 행정비 + 예방 정비 인건비 + 보관비)",
                                     className="mn-chart-note"),
                              graph("mn-saving-graph", saving_figure(history(as_of)), "clamp(240px,28vh,320px)")],
                             className="mn-hist-chart"),
                ], className="mn-hist-grid"),
            ], className="mn-block mn-history mn-band", id="mn-history"),
            html.Small("현재 상황·달력·TOP5·하단 그래프는 UI 확인용 예시 데이터입니다.", className="mn-sample-note"),

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
            ], id="mn-action-modal", is_open=False, centered=True, size="sm", className="mn-modal"),

            # 현재 상황 카드 상세 / 급상승 전체보기
            dbc.Modal([
                dbc.ModalHeader(dbc.ModalTitle(id="mn-more-title")),
                dbc.ModalBody(id="mn-more-body"),
            ], id="mn-more-modal", is_open=False, centered=True, size="lg", className="mn-modal"),
        ],
        className="mn-page",
    )

layout = build_layout(UI_AS_OF)


def create_main_layout(as_of=UI_AS_OF):
    return build_layout(as_of, make_f03_panel(as_of))


@callback(
    Output("mn-f02-slot", "className"),
    Output("mn-middle", "className"),
    Output("mn-show-top5", "children"),
    Input("mn-show-top5", "n_clicks"),
    Input("mn-close-top5", "n_clicks"),
    State("mn-middle", "className"),
    prevent_initial_call=True,
)
def toggle_top5(_show, _close, middle_class):
    opened = False if ctx.triggered_id == "mn-close-top5" else "mn-middle-open" not in (middle_class or "")
    slot, middle = TOP5_OPEN if opened else TOP5_CLOSED
    return slot, middle, "우선 확인 TOP5 닫기" if opened else "우선 확인 TOP5 보기"


@callback(
    Output("mn-calendar-body", "children"),
    Output("mn-top5-panel", "children"),
    Input("store-todo-dismissed", "data"),
    Input("mn-top5-sort", "value"),
    Input("store-as-of", "data"),
)
def render_todo(dismissed, sort, as_of):
    as_of = valid_as_of(as_of)
    items = ranked_items(dismissed, sort, as_of)
    top = items[:TOP_N]
    ranks = {item["key"]: rank for rank, item in enumerate(top, 1)}
    return make_calendar(items, ranks, as_of), make_top5(top, len(dismissed or []), as_of)


@callback(
    Output("mn-history-graph", "figure"),
    Output("mn-saving-graph", "figure"),
    Output("mn-history-rate", "children"),
    Output("mn-hist-custom", "className"),
    Input("store-order-log", "data"),
    Input("store-as-of", "data"),
    Input("mn-hist-range", "value"),
    Input("mn-hist-start", "value"),
    Input("mn-hist-end", "value"),
)
def render_history(orders, as_of, choice, start, end):
    as_of = valid_as_of(as_of)
    start, end = hist_bounds(as_of, choice, start, end)
    rows = history(as_of, orders, start, end)
    custom = "mn-hist-custom" + ("" if choice == "custom" else " is-hidden")
    return rate_figure(rows), saving_figure(rows), history_summary(rows), custom


@callback(
    Output("mn-more-modal", "is_open"),
    Output("mn-more-title", "children"),
    Output("mn-more-body", "children"),
    Input({"type": "mn-kpi", "key": ALL}, "n_clicks"),
    Input("mn-f01-more", "n_clicks"),
    State("store-as-of", "data"),
    prevent_initial_call=True,
)
def show_more(_kpis, _f01, as_of):
    trigger = ctx.triggered_id
    if not ctx.triggered or not ctx.triggered[0]["value"]:
        raise PreventUpdate
    if trigger == "mn-f01-more":
        return True, "확률 급상승 알림 · 전체", f01_full_table()
    key = trigger["key"]
    title, value, unit = next((t, v, u) for k, t, _, v, u, _, _ in KPIS if k == key)
    return True, f"{title} {value}{unit}", kpi_table(kpi_detail(key, valid_as_of(as_of)))


@callback(
    Output("mn-action-modal", "is_open"),
    Output("mn-action-key", "data"),
    Output("mn-action-body", "children"),
    Output("mn-action-detail", "href"),
    Input({"type": "mn-cal-item", "key": ALL}, "n_clicks"),
    Input({"type": "mn-top5-card", "key": ALL}, "n_clicks"),
    Input("mn-action-cancel", "n_clicks"),
    Input("mn-action-delete", "n_clicks"),
    State("store-as-of", "data"),
    prevent_initial_call=True,
)
def open_action(_cal, _cards, _cancel, _delete, as_of):
    trigger = ctx.triggered_id
    if trigger in ("mn-action-cancel", "mn-action-delete"):
        return False, None, no_update, no_update
    # 항목이 다시 그려질 때도 호출되므로 실제 클릭(n_clicks > 0)만 처리
    if not isinstance(trigger, dict) or not ctx.triggered[0]["value"]:
        raise PreventUpdate
    item = item_by_key(trigger["key"], valid_as_of(as_of))
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
