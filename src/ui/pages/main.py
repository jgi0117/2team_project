from __future__ import annotations

from dash import ALL, Input, Output, State, callback, ctx, dcc, html
import plotly.graph_objects as go

from src.F01 import build_detection
from src.F02 import build_procurement
from src.F04 import build_tracking
from src.ui.ai_data import f03_summary
from src.ui.config import UI_AS_OF


def dashboard_overview(as_of=None):
    """Compose the main page through the public feature packages."""
    as_of = UI_AS_OF if as_of is None else as_of
    detection = build_detection(as_of)
    procurement = build_procurement(as_of)
    tracking = build_tracking(as_of)
    return {
        "as_of": detection["as_of"], "previous_as_of": detection["previous_as_of"],
        "model_version": detection["model_version"], "calibrated": detection["calibrated"],
        "surges": detection["surges"], "anomaly_map": detection["anomaly_map"],
        "warning_policy": detection["warning_policy"],
        "warning_machine_ids": detection["warning_machine_ids"],
        "plan": procurement["plan"], "top5": procurement["top5"],
        "priority_equipment": procurement["priority_equipment"],
        "replacement_due_rows": procurement["replacement_due_rows"],
        "order_due_rows": procurement["order_due_rows"],
        "part_risk": procurement["part_risk"], "kpis": procurement["kpis"],
        "order_schedule": procurement["order_schedule"],
        "action_schedule": procurement["action_schedule"],
        "schedule_start": procurement["schedule_start"],
        "schedule_end": procurement["schedule_end"],
        "history": tracking["history"], "recent_actions": tracking["recent_actions"],
    }


def make_calendar(overview):
    month = overview["as_of"].to_period("M")
    today = int(overview["as_of"].day)
    events = {int(row.date.day): row.label
              for row in overview["action_schedule"].itertuples(index=False)}
    cells = []
    for day in range(1, month.days_in_month + 1):
        labels = [html.Span(str(day))]
        if day == today:
            labels.append(html.Small("오늘(기준일)", className="mn-today-label"))
        if day in events:
            labels.append(html.Small(events[day]))
        cells.append(html.Button(
            labels, id={"type": "mn-date", "date": f"{month}-{day:02d}"},
            className="mn-calendar-cell mn-calendar-today" if day == today else "mn-calendar-cell",
            **({"aria-current": "date"} if day == today else {}),
        ))
    return html.Div([
        html.Div([html.Div(day) for day in ["일", "월", "화", "수", "목", "금", "토"]], className="mn-week"),
        html.Div(cells, className="mn-calendar"),
        html.Button("우선 확인 설비 10건 보기", id="mn-show-top5", className="mn-action-btn"),
    ])


def make_top5(rows):
    status_labels = {
        "late": "일정 즉시 조정", "order_due": "발주 확인",
        "watch": "발주 준비", "covered": "재고 대응 가능",
    }
    return html.Div([
        html.Div([html.Strong("우선 확인 설비 10건")], className="mn-top5-header"),
        html.Div([dcc.Link([
            html.Span(str(rank), className="mn-rank"),
            html.Strong(f"M-{int(row.machineID):03d} · {row.component}"),
            html.Span(f"{status_labels.get(row.status, '상태 확인')} · 위험 {row.risk_score:.3f}"),
        ], href=f"/detail?machine={int(row.machineID)}", className="mn-top5-row")
            for rank, row in enumerate(rows.itertuples(index=False), 1)], id="mn-top5-list"),
        html.Small("부품별 위험 상위 5% 중 조치 상태·위험 점수 순", className="mn-guide"),
    ], className="box mn-f02")


def make_summary_cards(overview):
    kpi = overview["kpis"]
    warning_links = [
        dcc.Link(f"M-{machine_id:03d}", href=f"/detail?machine={machine_id}")
        for machine_id in overview["warning_machine_ids"]
    ]
    replacement_links = [dcc.Link(
        f"M-{int(row.machineID):03d} · {row.component} · {row.target_maintenance_at:%m-%d}",
        href=f"/detail?machine={int(row.machineID)}",
    ) for row in overview["replacement_due_rows"].itertuples(index=False)]
    order_links = [dcc.Link(
        f"M-{int(row.machineID):03d} · {row.component} · 마감 {row.order_by_at:%m-%d}",
        href=f"/detail?machine={int(row.machineID)}",
    ) for row in overview["order_due_rows"].itertuples(index=False)]
    cards = [
        ("경고 설비", f"{kpi['warning_machines']}대", "mn-summary-red", warning_links,
         "경고 설비 상세 보기"),
        ("교체기한 임박", f"{kpi['replacement_due']}건", "mn-summary-blue", replacement_links,
         "14일 이내 정비 예정"),
        ("기한 초과", f"{kpi['late_items']}건", "mn-summary-red", None, None),
        ("이번 주 발주 필요", f"{kpi['order_due']}건", "", order_links,
         "발주 확인 대상"),
        ("14일 지연 대비 절감 효과", format_won(kpi["action_savings"]),
         "mn-summary-green", None, None),
    ]
    return html.Div([html.Div([
        html.Div(title, className="mn-summary-title"),
        html.Div(html.Strong(value), className="mn-summary-value"),
        html.Div([html.Strong(hover_title), *links], className="mn-card-hover")
        if links else None,
    ], className=f"mn-summary-card {extra} {'mn-summary-card-clickable' if links else ''}".strip(),
       tabIndex=0 if links else None)
        for title, value, extra, links, hover_title in cards], className="mn-summary-cards")


def format_won(value):
    value = float(value)
    if abs(value) >= 100_000_000:
        return f"{value / 100_000_000:,.1f}억원"
    return f"{value / 10_000:,.0f}만원"


def make_f03_panel():
    try:
        result = f03_summary()
    except (OSError, ValueError, KeyError, IndexError):
        result = {"text": "고장 예측 결과를 불러오지 못했습니다.", "selected": None,
                  "prediction_as_of": None, "horizon_days": None}
    details = []
    selected = result.get("selected")
    if selected:
        details.append(dcc.Link(f"설비 M-{selected['machineID']:03d} 상세 보기",
                                href=f"/detail?machine={selected['machineID']}", className="mn-f03-link"))
    text = format_priority_summary(result)
    return html.Div([html.Strong("오늘의 우선 대응 요약"), html.Span(text, id="mn-summary"),
                     html.Div(details, className="mn-f03-meta")], className="mn-f03", id="mn-f03")


def format_priority_summary(result):
    text = str(result.get("text") or "").strip()
    parts = [part.strip().rstrip(".") for part in text.split(";") if part.strip()]
    if len(parts) > 1:
        return f"{parts[0]}. 근거: {' · '.join(parts[1:])}."
    selected = result.get("selected")
    if selected and "근거:" not in text:
        score = selected.get("failure_probability")
        calibrated = bool(selected.get("calibrated"))
        if score is not None:
            risk = f"고장 확률 {score:.1%}" if calibrated else f"미보정 고장 위험 점수 {score:.3f}"
            return f"{text.rstrip('.')}. 근거: {risk}."
    return text


def surge_figure(overview):
    rows = overview["surges"]
    labels = [f"M-{int(row['machineID']):03d}" for row in rows]
    values = [row["change"] for row in rows]
    current = [row["failure_probability"] for row in rows]
    figure = go.Figure(go.Bar(
        x=labels, y=values, customdata=[[row["machineID"], score]
                                       for row, score in zip(rows, current)],
        marker_color=["#ef4444", "#f97316", "#f59e0b"],
        text=[f"{v:+.3f}" for v in values], textposition="outside",
        hovertemplate=("설비 %{x}<br>현재 위험 점수 %{customdata[1]:.3f}"
                       "<br>전일 대비 %{y:+.3f}<extra></extra>"),
    ))
    figure.update_layout(margin={"l": 45, "r": 10, "t": 20, "b": 35}, height=220,
                         yaxis_title="위험 점수 변화", showlegend=False,
                         paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    return figure


def inventory_table(overview):
    table = html.Table([
        html.Thead(html.Tr([html.Th("부품"), html.Th("가용재고"),
                            html.Th("위험 설비"), html.Th("재고 대비 부족"),
                            html.Th("목표재고 보충"), html.Th("즉시 확인"),
                            html.Th("최대 위험점수")])),
        html.Tbody([html.Tr([html.Td(row.component), html.Td(int(row.available_stock)),
                            html.Td(f"{int(row.risk_machines)}대"),
                            html.Td(f"{int(row.demand_shortage)}개"),
                            html.Td(f"{int(row.replenishment_qty)}개"),
                            html.Td(f"{int(row.urgent)}건"),
                            html.Td(f"{row.max_risk:.3f}")])
                    for row in overview["part_risk"].itertuples(index=False)])
    ], className="mn-data-table")
    return html.Div(table, className="mn-table-scroll")


def history_figure(overview):
    data = overview["history"]
    figure = go.Figure(go.Scatter(
        x=data.period, y=data.response_rate * 100, name="예방 대응률",
        mode="lines+markers", line={"color": "#16a34a", "width": 3},
        marker={"size": 7}, hovertemplate="%{x}<br>대응률 %{y:.1f}%<extra></extra>",
    ))
    figure.update_layout(margin={"l": 50, "r": 20, "t": 20, "b": 35}, height=230,
                         yaxis={"title": "대응률(%)", "range": [0, 100]}, showlegend=False,
                         paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    return figure


def create_main_layout():
    overview = dashboard_overview()
    calibration = "보정 확률" if overview["calibrated"] else "미보정 위험 점수"
    return html.Div([
        html.Div([html.H2("설비보전 관리 대시보드"),
                  html.Span(f"기준일 {overview['as_of']:%Y-%m-%d}")], className="mn-page-header"),
        make_f03_panel(),
        html.Div([
            html.Div([html.Strong("현재 상황"),
                      html.Small(overview["warning_policy"], className="mn-caption"),
                      html.Small(f"비용은 우선 대응 {overview['kpis']['cost_scope']}건 기준", className="mn-caption"),
                      make_summary_cards(overview)], className="box mn-current-summary"),
            html.Div([html.Strong("월간 확인·조치 일정"),
                      html.P(f"{overview['schedule_start']:%Y년 %m월}"),
                      make_calendar(overview)], className="box mn-todo"),
            html.Div([html.Div(id="mn-top5-panel"),
                      html.Button("목록 닫기", id="mn-close-top5", className="mn-action-btn mn-close-btn")],
                     id="mn-f02-slot", className="mn-f02-slot mn-f02-slot-closed"),
        ], id="mn-middle", className="mn-middle-grid mn-middle-closed"),
        html.Div([
            html.Div([html.Strong("전일 대비 고장 확률 급상승 TOP3"),
                      html.Small(f"당일 위험도 상위 5% 중 상승 폭 기준 · {calibration}", className="mn-caption"),
                      dcc.Graph(id="mn-surge-graph", figure=surge_figure(overview),
                                config={"displayModeBar": False}, className="mn-surge-graph")], className="box mn-bottom-box"),
            html.Div([html.Strong("부품별 재고·조달 위험"), inventory_table(overview)], className="box mn-bottom-box"),
        ], className="mn-bottom-grid"),
        html.Div([html.Strong("월별 예방 대응률"),
                  html.Small("전체 정비 중 고장 전에 수행한 예방 정비 비율", className="mn-caption"),
                  dcc.Graph(figure=history_figure(overview), config={"displayModeBar": False})],
                 className="box mn-history", id="mn-history"),
    ], className="mn-page")


# Callback registration does not require eager data/model loading. The app route
# calls create_main_layout() and receives the populated page.
layout = html.Div([html.Div(id="mn-f03")])


@callback(Output("mn-top5-panel", "children"), Output("mn-f02-slot", "className"), Output("mn-middle", "className"),
          Input("mn-show-top5", "n_clicks"), Input("mn-close-top5", "n_clicks"),
          State({"type": "mn-date", "date": ALL}, "n_clicks"), prevent_initial_call=True)
def toggle_top5(show_click, close_click, date_clicks):
    if ctx.triggered_id == "mn-close-top5":
        return [], "mn-f02-slot mn-f02-slot-closed", "mn-middle-grid mn-middle-closed"
    overview = dashboard_overview()
    return make_top5(overview["priority_equipment"]), \
        "mn-f02-slot mn-f02-slot-open", "mn-middle-grid mn-middle-open"
