# src/ui/pages/detail/page.py
# 설비 상세. 시선 흐름: ① 설비 상태(좌상단) → ② 부품 위치·위험(도면 위 말풍선) → ③ 이유(AI 진단)
#                     → ④ 근거(센서 이상) → ⑤ 행동(발주 검토 → 발주 정보 → 교체 이력)
from functools import lru_cache

import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
from dash import html, dcc, Input, Output, State, ALL, callback, ctx
from dash.exceptions import PreventUpdate
from plotly.subplots import make_subplots

from src.common.paths import PROCESSED
from src.F09.heatmap import load_predictions, machine_ids
from src.ui import detail_data
from src.ui.ai_data import f05_diagnosis, f06_analysis
from src.ui.config import UI_AS_OF, upto_as_of, valid_as_of
from src.ui.sample_data import ranked_items

PREDICTIONS = load_predictions()
MACHINES = machine_ids()
AS_OF = upto_as_of(PREDICTIONS).as_of.max()

COMPS    = ["comp1", "comp2", "comp3", "comp4"]
DECISION = {"comp1": 8, "comp2": 42, "comp3": 16, "comp4": 24}
ADOPTED  = {"comp1": True, "comp2": False, "comp3": True, "comp4": True}
HORIZONS = [7, 8, 14, 16, 21, 24, 28, 35, 42]
SENSOR_NAMES = {"volt": "전압", "rotate": "회전속도", "pressure": "압력", "vibration": "진동"}

# 위험 판정 (risk_curve.csv의 risk_status) → 화면 색 클래스
STATUS_CLASS = {"즉시": "now", "주의": "watch", "관찰": "ok", "정상": "calm"}

# 차트 색: 00_tokens.css와 같은 값 (Plotly는 CSS 변수를 읽지 못함)
NAVY, NAVY_SOFT, YELLOW, YELLOW_DARK, DANGER = "#003566", "#7f9bbd", "#ffc300", "#c99a00", "#d62839"
MUTED, GRID, INK = "#8a94a6", "#e3e7ed", "#0f1a2b"
FONT = "NanumSquare Neo, Malgun Gothic, sans-serif"

# 설비 그림 위 부품 좌표(%) — 그림 기준. 그림이 바뀌면 이 숫자만 수정
POS = {
    "comp1": {"top": "16%", "left": "22%"},
    "comp2": {"top": "26%", "left": "62%"},
    "comp3": {"top": "58%", "left": "32%"},
    "comp4": {"top": "68%", "left": "72%"},
}
# 말풍선 방향 (점 기준): above / right / below — 서로 겹치거나 그림 밖으로 나가지 않게
PLACE = {"comp1": "right", "comp2": "above", "comp3": "above", "comp4": "above"}


@lru_cache(maxsize=1)
def risk_curve():
    """부품별 위험 상승 예상 시점과 판정 (모델 산출물)."""
    return pd.read_csv(PROCESSED / "risk_curve.csv")


def machine_risk(machine_id, as_of):
    """기준일 직전 예측의 부품별 행 {comp: row}."""
    data = risk_curve()
    data = data.loc[data.machineID.eq(machine_id) & data.as_of.le(as_of)]
    if data.empty:
        return {}
    data = data.loc[data.as_of.eq(data.as_of.max())]
    return {row.component: row for row in data.itertuples()}


def rise_days(row):
    days = getattr(row, "risk_rise_from_days", None)
    return None if days is None or pd.isna(days) else int(round(days))


def d_label(days):
    return "—" if days is None else ("D-day" if days <= 0 else f"D-{days}")


def won(value):
    return f"{value:,.0f}만원"


def section_head(title, *extra):
    return html.Div([html.H2(title), *extra], className="dt-section-head")


def status_badge(status):
    return html.Span(status, className=f"dt-status dt-status--{STATUS_CLASS.get(status, 'calm')}")


def ghost(text, min_h=80):
    return html.Div(text, className="ghost", style={"minHeight": f"{min_h}px"})


def figure_base():
    figure = go.Figure()
    figure.update_layout(margin={"l": 8, "r": 12, "t": 12, "b": 8}, showlegend=False,
                         paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                         font={"family": FONT, "size": 12, "color": MUTED},
                         hoverlabel={"font": {"family": FONT}})
    return figure


# ---------------- ② 도면 위 부품 말풍선 ----------------
def hotspot(comp):
    on = ADOPTED[comp]
    state = ("hotspot--on" if on else "hotspot--off") + f" hotspot--{PLACE.get(comp, 'above')}"

    dot = html.Div(className=f"hotspot-dot {state}", style=POS[comp])

    # 말풍선 전체가 hotspot-{comp} 클릭 영역. 안의 '발주 검토' 표시는 누를 수 있다는 안내.
    bubble = html.Div(
        id=f"hotspot-{comp}", n_clicks=0, className=f"hotspot {state}",
        style=POS[comp], role="button", tabIndex="0",
        children=[
            html.Div([
                html.Span(comp, id=f"hs-name-{comp}", className="hs-name"),
                html.Span(f"{DECISION[comp]}일 기준", id=f"hs-horizon-{comp}", className="hs-horizon"),
            ], className="hs-head"),
            html.Div("--", id=f"hs-prob-{comp}", className="hotspot-prob"),
            html.Div("" if on else "안전재고로 대응", className="hs-note"),
            html.Span("발주 검토 →", className="hs-order"),
        ],
    )

    pop = dbc.Popover(
        [dbc.PopoverHeader(f"{comp} 기간별 고장 위험 점수"),
         dbc.PopoverBody([
             html.Div(className="pop-scroll", children=html.Div(
                 id=f"hs-pop-table-{comp}",
                 children=html.Table([
                     html.Thead(html.Tr([html.Th("기간")] + [html.Th(f"{h}일") for h in HORIZONS])),
                     html.Tbody(html.Tr([html.Td("점수")] + [html.Td("--") for _ in HORIZONS])),
                 ], className="hs-pop-table"))),
             html.Small("다른 설비와 비교한 상대 점수입니다(확률 아님). 누르면 발주 검토가 열립니다.",
                        className="hs-pop-note"),
         ])],
        id=f"hs-pop-{comp}", target=f"hotspot-{comp}",
        trigger="hover", placement="auto", className="hs-pop",
    )
    return [dot, bubble, pop]


# ---------------- 캔버스: 은은한 설비 그림 + 떠 있는 정보 ----------------
def canvas(selected, as_of):
    return html.Section(className="dt-canvas", children=[
        # 배경: 설비 그림 + 부품 말풍선
        html.Div(id="dt-drawing", className="dt-drawing", children=[
            html.Div(id="f05-equip-img", className="stage-bg",
                     children=html.Img(src="/assets/equipment-comp-layout.png",
                                       alt="4개 부품 위치가 표시된 산업용 설비")),
            *[el for c in COMPS for el in hotspot(c)],
        ]),
        # 보기 전환: 도면 / 4개 부품 기간별 전체
        html.Div(dcc.RadioItems(
            id="dt-view", value="drawing", inline=True, className="dt-seg",
            options=[{"label": "부품 위치", "value": "drawing"},
                     {"label": "4개 부품 기간별 위험", "value": "table"}],
        ), className="dt-view-switch"),
        html.Div(id="dt-horizon-panel", className="dt-horizon-panel is-hidden", children=[
            html.Div([html.H3("부품별 · 기간별 고장 위험 점수"),
                      html.Span("노란 테두리 = 부품별 발주 결정 시한 · 진할수록 위험 · 상대 점수(확률 아님)",
                                className="dt-panel-hint")],
                     className="dt-horizon-head"),
            html.Div(id="dt-horizon-table", className="table-scroll"),
        ]),

        # ① 좌상단: 설비와 상태
        html.Div(id="f05-summary", className="dt-head", children=[
            html.Div([
                html.Span("설비 상세", className="hdr-title"),
                dcc.Dropdown(
                    id="detail-machine-select",
                    options=[{"label": f"M-{machine:03d}", "value": machine} for machine in MACHINES],
                    value=selected, clearable=False, searchable=True,
                    className="detail-machine-select",
                ),
            ], className="dt-head-top"),
            html.H1(f"M-{selected:03d}", id="detail-machine-name", className="hdr-machine"),
            html.Span("위험 상승 예상", className="dt-kicker"),
            html.Div("--", id="f05-summary-days", className="summary-days"),
            html.Div("부품별 위험 비교", id="f05-summary-note", className="summary-sub"),
            html.Div([
                html.Div([html.Span("센서 이상 신호 · 72시간"),
                          html.Div("--", id="dt-sensor-count", className="dt-mini-value")], className="dt-mini"),
                html.Div([html.Span("기준일"),
                          html.Div(as_of, id="detail-asof", className="dt-mini-value")], className="dt-mini"),
            ], className="dt-mini-row"),
        ]),

        # 우상단: 행동 버튼
        html.Div(className="dt-actions", children=[
            html.Button("발주 정보 0건", id="dt-cart-btn", n_clicks=0, className="dt-btn"),
            html.Button("교체 이력", id="btn-open-history", n_clicks=0, className="dt-btn"),
        ]),

        # ③ 좌하단: AI 종합 진단
        html.Div(className="dt-ai", children=[
            html.Span("AI 종합 진단", className="dt-ai-badge"),
            html.Div("종합진단을 준비하고 있습니다", id="f05-summary-basis", className="dt-ai-text"),
        ]),

        # ④로 이어지는 우하단: 센서 이상 추이 미리보기
        html.A(href="#dt-sensor", className="dt-trend", children=[
            html.Div([html.Span("센서 이상 · 시간별 건수"), html.Span("자세히 ↓", className="dt-trend-link")],
                     className="dt-trend-head"),
            dcc.Graph(id="dt-sensor-spark", figure=figure_base(),
                      config={"displayModeBar": False, "staticPlot": True}, style={"height": "78px"}),
        ]),
    ])


# ---------------- ④ 센서 이상 근거 ----------------
def legend_item(kind, label):
    return html.Span([html.I(className=f"dt-lg dt-lg--{kind}"), label], className="dt-legend-item")


f06_overlay = html.Section(
    id="f06-overlay", className="dt-band dt-f06",
    children=[
        html.Span(id="dt-sensor", className="dt-anchor"),
        section_head("센서 이상 근거",
                     html.Div([html.Label("센서", htmlFor="f06-sensor-select", className="dt-select-label"),
                               dcc.Dropdown(
                                   id="f06-sensor-select",
                                   options=[{"label": f"{label} ({sensor})", "value": sensor}
                                            for sensor, label in SENSOR_NAMES.items()],
                                   value="vibration", clearable=False, searchable=False,
                                   className="f06-sensor-select",
                               )], className="dt-select-row")),
        html.Div(className="dt-f06-grid", children=[
            html.Div(className="dt-f06-main", children=[
                html.Div(id="f06-alert-summary", className="f06-alert-summary"),
                html.Div([legend_item("value", "관측값"), legend_item("iqr", "IQR 탐지 상·하한"),
                          legend_item("sigma", "3σ 관리 상·하한"), legend_item("alert", "이상"),
                          legend_item("if", "IF 점수 / 기준")], className="dt-legend"),
                dcc.Graph(id="f06-sensor-graph", figure={}, responsive=True,
                          config={"displayModeBar": False},
                          style={"height": "clamp(300px,40vh,440px)"}),
                html.Small(id="f06-observed", className="f06-observed"),
            ]),
            html.Div(className="dt-f06-side", children=[
                html.Div([html.H3("설비 전체 IF 이상 점수"),
                          html.Div(id="f06-if-score", children=ghost("IF 점수", 84))], className="dt-side-block"),
                html.Div([html.H3("센서별 판정 (현재 시점)"),
                          html.Div(id="f06-reason-table", children=ghost("센서별 판정", 84), className="table-scroll")],
                         className="dt-side-block"),
            ]),
        ]),
    ],
)

# ---------------- ⑤ 발주 검토 ----------------
f07_panel = dbc.Collapse(
    id="f07-collapse", is_open=False,
    children=html.Section(className="dt-band dt-panel", children=[
        section_head(
            html.Span(["발주 시점 · 비용 검토 ", html.Span("--", id="f07-part-label", className="f07-part-label")]),
            html.Div(className="btns", children=[
                html.Button("발주 정보 보기", id="btn-add-cart", n_clicks=0, className="dt-btn dt-btn--primary"),
                html.Button("닫기", id="btn-f07-close", n_clicks=0, className="dt-btn"),
            ])),
        html.Div(className="dt-f07-grid", children=[
            html.Div(className="dt-f07-block", children=[
                html.H3("언제 발주하면 가장 쌀까"),
                html.P("발주일별 예상 총비용 · 너무 이르면 보관비, 늦으면 고장 후 긴급 대응 비용이 커집니다",
                       className="dt-block-note"),
                dcc.Graph(id="f07-cost-curve", figure=figure_base(), responsive=True,
                          config={"displayModeBar": False}, style={"height": "clamp(200px,24vh,260px)"}),
            ]),
            html.Div(className="dt-f07-block", children=[
                html.H3("발주 · 재고 정보"),
                html.Div(id="f07-order-info", children=ghost("부품을 선택하세요", 150)),
            ]),
            html.Div(className="dt-f07-block", children=[
                html.H3("발주 시나리오 비교"),
                html.Div(className="dt-scenarios", children=[
                    html.Div(["오늘 발주", html.Div("--", id="f07-cost-d0", className="f07-scenario-value")],
                             className="f07-scenario"),
                    html.Div(["1주 뒤", html.Div("--", id="f07-cost-d7", className="f07-scenario-value")],
                             className="f07-scenario"),
                    html.Div(["2주 뒤", html.Div("--", id="f07-cost-d14", className="f07-scenario-value")],
                             className="f07-scenario"),
                ]),
                html.P("예상 총비용 기준 · 가장 낮은 안에 '최저' 표시", className="dt-block-note"),
            ]),
        ]),
    ]),
)

# ---------------- ⑤ 발주 정보 (장바구니처럼 누적) ----------------
f08_supplier = dbc.Collapse(
    id="f08-supplier-collapse", is_open=False,
    children=html.Section(className="dt-band dt-panel", children=[
        section_head("발주 정보",
                     html.Div(className="btns", children=[
                         html.Button("비우기", id="f08-clear", n_clicks=0, className="dt-btn"),
                         html.Button("닫기", id="btn-f08-supplier-close", n_clicks=0, className="dt-btn"),
                     ])),
        html.Div(id="f08-supplier-body", children=ghost("발주 검토에서 '발주 정보 보기'를 누르면 부품별로 쌓입니다", 100)),
    ]),
)

# ---------------- ⑤ 교체 이력 ----------------
f08_history = dbc.Collapse(
    id="f08-history-collapse", is_open=False,
    children=html.Section(className="dt-band dt-panel", children=[
        section_head("교체 이력",
                     html.Div(html.Button("닫기", id="btn-f08-history-close", n_clicks=0, className="dt-btn"),
                              className="btns")),
        html.Div(id="f08-history-table", children=ghost("교체일 / 부품 / 구분 / 담당자 / 비용", 130)),
    ]),
)


# ---------------- layout ----------------
def create_detail_layout(machine_id=None, as_of=None):
    selected = machine_id if machine_id in MACHINES else MACHINES[0]
    as_of = valid_as_of(as_of)
    return html.Div(className="page-detail", children=[
        dcc.Store(id="store-selected-machine", data=selected),
        dcc.Store(id="store-selected-comp", data=None),
        dcc.Store(id="f08-last-order"),
        dcc.ConfirmDialog(id="f07-confirm-dismiss"),

        canvas(selected, as_of),
        f06_overlay,
        f07_panel,
        f08_supplier,
        f08_history,
        html.P("고장 위험은 부품별 예측 모델, 센서 이상은 별도의 이상 탐지 결과입니다. "
               "발주 검토·발주 정보의 비용과 업체는 가상 운영 데이터 기반 예시이며, 교체 이력은 원본 정비 기록입니다.",
               className="detail-frame-note"),
    ])


layout = create_detail_layout()


def resolve_as_of(as_of):
    return valid_as_of(as_of) if as_of else AS_OF


def part_rows(machine_id, as_of):
    risk = machine_risk(machine_id, as_of)
    rows = []
    for comp in COMPS:
        row = risk.get(comp)
        days = rise_days(row) if row is not None else None
        status = getattr(row, "risk_status", "정상") if row is not None else "정상"
        rows.append({"comp": comp, "days": days, "status": status, "adopted": ADOPTED[comp]})
    return rows


@callback(
    Output("detail-machine-name", "children"),
    Output("store-selected-machine", "data"),
    *[Output(f"hs-prob-{comp}", "children") for comp in COMPS],
    Output("f05-summary-days", "children"),
    Output("f05-summary-note", "children"),
    Output("f05-summary-basis", "children"),
    Input("detail-machine-select", "value"),
    State("store-as-of", "data"),
)
def show_machine(machine_id, as_of=None):
    as_of = resolve_as_of(as_of)
    parts = part_rows(machine_id, as_of)
    bubbles = []
    for part in parts:
        if not part["adopted"]:
            bubbles.append(html.Span("미채택", className="hs-dday is-off"))
        else:
            bubbles.append([html.Span(d_label(part["days"]), className="hs-dday"),
                            status_badge(part["status"])])
    # 설비 D-day: 예측을 채택한 부품 중 위험이 가장 먼저 오르는 부품
    rising = sorted((part for part in parts if part["adopted"] and part["days"] is not None),
                    key=lambda part: part["days"])
    if rising:
        first = rising[0]
        days = d_label(first["days"])
        note = f"{first['comp']} · 판정 {first['status']} · {DECISION[first['comp']]}일 발주 결정 시한"
    else:
        days, note = "안정", f"{max(HORIZONS)}일 안에 위험 상승이 예상되는 부품 없음"
    try:
        diagnosis = f05_diagnosis(int(machine_id), as_of)
    except (OSError, ValueError, KeyError):
        basis = "종합진단 자료를 읽지 못했습니다"
    else:
        basis = diagnosis["text"]
    return f"M-{machine_id:03d}", machine_id, *bubbles, days, note, basis


@callback(
    Output("dt-horizon-table", "children"),
    *[Output(f"hs-pop-table-{comp}", "children") for comp in COMPS],
    Input("detail-machine-select", "value"),
    State("store-as-of", "data"),
)
def show_parts(machine_id, as_of):
    """부품별 기간 점수: 팝오버(부품 하나)와 '4개 부품 기간별 위험' 보기(전체)."""
    as_of = resolve_as_of(as_of)
    preds = upto_as_of(PREDICTIONS, as_of)
    preds = preds.loc[preds.machineID.eq(machine_id)]
    latest = preds.loc[preds.as_of.eq(preds.as_of.max())]
    scores = {comp: latest.loc[latest.component.eq(comp)].set_index("horizon_days").failure_probability
              for comp in COMPS}
    top = max([value for series in scores.values() for value in series.dropna()] or [1])

    def cell(comp, h):
        value = scores[comp].get(h)
        missing = value is None or pd.isna(value)
        level = 0 if missing else min(int(value / top * 5), 4)
        return html.Td("--" if missing else f"{value:.2f}",
                       className=f"dt-heat dt-heat--{level}" + (" is-decision" if h == DECISION[comp] else ""))

    parts = {part["comp"]: part for part in part_rows(machine_id, as_of)}
    table = html.Table([
        html.Thead(html.Tr([html.Th("부품")] + [html.Th(f"{h}일") for h in HORIZONS]
                           + [html.Th("위험 상승"), html.Th("")])),
        html.Tbody([
            html.Tr([html.Td(html.B(comp))] + [cell(comp, h) for h in HORIZONS] + [
                html.Td(d_label(parts[comp]["days"]) if ADOPTED[comp] else "미채택"),
                html.Td(html.Button("발주 검토 →", id={"type": "dt-part-order", "comp": comp},
                                    className="dt-row-action")),
            ], className="" if ADOPTED[comp] else "is-off")
            for comp in COMPS
        ]),
    ], className="dt-table dt-heat-table")

    pops = []
    for comp in COMPS:
        pops.append(html.Table([
            html.Thead(html.Tr([html.Th("기간")] + [
                html.Th(f"{h}일", className="is-decision" if h == DECISION[comp] else "") for h in HORIZONS])),
            html.Tbody(html.Tr([html.Td("점수")] + [
                html.Td("--" if h not in scores[comp] or pd.isna(scores[comp][h]) else f"{scores[comp][h]:.2f}",
                        className="is-decision" if h == DECISION[comp] else "") for h in HORIZONS])),
        ], className="hs-pop-table"))
    return table, *pops


@callback(
    Output("dt-horizon-panel", "className"),
    Output("dt-drawing", "className"),
    Input("dt-view", "value"),
)
def switch_view(view):
    table = view == "table"
    return ("dt-horizon-panel" + ("" if table else " is-hidden"),
            "dt-drawing" + (" is-dimmed" if table else ""))


def f06_sensor_figure(result, sensor):
    if sensor not in SENSOR_NAMES:
        sensor = "vibration"
    figure = make_subplots(rows=2, cols=1, shared_xaxes=True,
                           row_heights=[.66, .34], vertical_spacing=.1)
    points = result.get("timeline", [])
    if not points:
        figure.add_annotation(text="시간별 관측 없음", x=0.5, y=0.5, xref="paper", yref="paper",
                              showarrow=False)
    else:
        x = [point["as_of"] for point in points]
        rows = [point.get("sensors", {}).get(sensor) for point in points]
        values = [None if row is None else row["value"] for row in rows]
        figure.add_trace(go.Scatter(x=x, y=values, mode="lines+markers", name=SENSOR_NAMES[sensor],
                                    line={"color": NAVY, "width": 2},
                                    marker={"size": 4, "color": NAVY}, connectgaps=False), row=1, col=1)
        for method, label, color, limits in (("iqr", "IQR", NAVY_SOFT, ("UDL", "LDL")),
                                             ("three_sigma", "3σ", YELLOW_DARK, ("UCL", "LCL"))):
            decisions = [None if row is None else row.get(method) for row in rows]
            for (bound, dash), limit_name in zip((("upper", "dash"), ("lower", "dot")), limits):
                figure.add_trace(go.Scatter(
                    x=x, y=[None if item is None else item[bound] for item in decisions],
                    mode="lines", name=f"{label} {limit_name}",
                    line={"color": color, "width": 1.5, "dash": dash}, connectgaps=False,
                    hovertemplate=f"%{{x}}<br>{label} {limit_name}: %{{y:.3f}}<extra></extra>",
                ), row=1, col=1)
            flagged = [(time, value) for time, value, item in zip(x, values, decisions)
                       if value is not None and item is not None and item["is_anomaly"]]
            figure.add_trace(go.Scatter(
                x=[item[0] for item in flagged], y=[item[1] for item in flagged],
                mode="markers", name=f"{label} 이상",
                marker={"color": DANGER, "size": 11, "symbol": "x" if method == "iqr" else "diamond",
                        "line": {"color": "white", "width": 1}},
                hovertemplate=f"%{{x}}<br>{label} 이상: %{{y:.3f}}<extra></extra>",
            ), row=1, col=1)
        if_results = [point.get("if") for point in points]
        figure.add_trace(go.Scatter(
            x=x, y=[None if item is None else item["anomaly_score"] for item in if_results],
            mode="lines+markers", name="IF 점수", line={"color": NAVY, "width": 2},
            marker={"size": 4, "color": NAVY}, connectgaps=False,
        ), row=2, col=1)
        figure.add_trace(go.Scatter(
            x=x, y=[None if item is None else item["threshold"] for item in if_results],
            mode="lines", name="IF 기준", line={"color": YELLOW_DARK, "width": 1.5, "dash": "dash"},
            connectgaps=False,
        ), row=2, col=1)
        flagged_if = [(time, item["anomaly_score"]) for time, item in zip(x, if_results)
                      if item is not None and item["is_anomaly"]]
        figure.add_trace(go.Scatter(
            x=[item[0] for item in flagged_if], y=[item[1] for item in flagged_if],
            mode="markers", name="IF 이상",
            marker={"color": DANGER, "size": 10, "line": {"color": "white", "width": 1.5}},
        ), row=2, col=1)
    figure.update_layout(
        margin={"l": 48, "r": 12, "t": 8, "b": 30}, showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font={"family": FONT, "size": 12, "color": MUTED},
        hoverlabel={"font": {"family": FONT}},
    )
    figure.update_xaxes(showgrid=False, tickformat="%m-%d %H시", nticks=6, linecolor=GRID)
    figure.update_yaxes(gridcolor=GRID, zeroline=False, title_text=SENSOR_NAMES[sensor], row=1, col=1)
    figure.update_yaxes(gridcolor=GRID, zeroline=False, title_text="IF", row=2, col=1)
    return figure


def f06_if_card(result):
    score = result.get("if")
    if score is None:
        return html.Div([html.Strong("결과 없음", className="f06-if-value is-empty"),
                         html.Small("이 시점의 IF 결과가 아직 없습니다 (2015-10-20부터 제공)")],
                        className="f06-if-card")
    alert = score["is_anomaly"]
    ratio = min(score["anomaly_score"] / (score["threshold"] * 1.6), 1) * 100
    return html.Div([
        html.Div([html.Strong(f"{score['anomaly_score']:.3f}", className="f06-if-value"),
                  html.Span("경고" if alert else "정상 범위",
                            className="dt-status dt-status--now" if alert else "dt-status dt-status--ok")],
                 className="f06-if-top"),
        html.Div([html.Div(className="f06-if-fill", style={"width": f"{ratio:.0f}%"}),
                  html.Div(className="f06-if-mark", style={"left": f"{100 / 1.6:.0f}%"})],
                 className="f06-if-bar" + (" is-alert" if alert else "")),
        html.Small(f"경고 기준 {score['threshold']:.3f} 초과 시 경고 · 확률 아님", className="f06-if-note"),
    ], className="f06-if-card")


def f06_reason_table(result):
    if not result.get("sensors"):
        return html.Div("센서 결과 없음", className="f06-empty")

    def decision(bounds):
        if bounds is None:
            return html.Td(html.Span("미확정", className="dt-status dt-status--calm"))
        alert = bounds["is_anomaly"]
        return html.Td(html.Span("이탈" if alert else "범위 내",
                                 className="dt-status dt-status--now" if alert else "dt-status dt-status--calm"),
                       title=f"기준 {bounds['lower']:.3f} ~ {bounds['upper']:.3f}")

    return html.Table([
        html.Thead(html.Tr([html.Th("센서"), html.Th("관측"), html.Th("3σ"), html.Th("IQR")])),
        html.Tbody([
            html.Tr([html.Td(SENSOR_NAMES[row["sensor"]]),
                     html.Td("—" if row["value"] is None else f"{row['value']:.2f}"),
                     decision(row["three_sigma"]), decision(row["iqr"])])
            for row in result["sensors"]
        ]),
    ], className="f06-table")


def f06_counts(result, sensor):
    points = result.get("timeline", [])
    counts, available = {}, {}
    for method in ("iqr", "three_sigma", "if"):
        decisions = [point.get("if") if method == "if" else
                     point.get("sensors", {}).get(sensor, {}).get(method) for point in points]
        counts[method] = sum(bool(item and item["is_anomaly"]) for item in decisions)
        available[method] = sum(item is not None for item in decisions)
    return counts, available


def f06_alert_summary(result, sensor):
    if sensor not in SENSOR_NAMES:
        sensor = "vibration"
    if not result.get("timeline", []):
        return html.Span("표시할 센서 관측이 없습니다", className="f06-summary-ok")
    counts, available = f06_counts(result, sensor)
    total = sum(counts.values())
    state = ("이상 없음" if all(available.values()) and not total else
             "판정 가능 시점에서 이상 없음" if not total else "이상 신호 있음")
    label = (f"최근 {result.get('window_hours', 72)}시간 · 선택 센서 IQR {counts['iqr']}건, "
             f"3σ {counts['three_sigma']}건 · 설비 IF {counts['if']}건 · {state}")
    return html.Span(label, className="f06-summary-alert" if total else "f06-summary-ok")


@callback(
    Output("f06-sensor-graph", "figure"),
    Output("f06-if-score", "children"),
    Output("f06-reason-table", "children"),
    Output("f06-alert-summary", "children"),
    Output("f06-observed", "children"),
    Input("detail-machine-select", "value"),
    Input("f06-sensor-select", "value"),
    State("store-as-of", "data"),
)
def show_f06(machine_id, sensor, as_of=None):
    if machine_id not in MACHINES:
        raise PreventUpdate
    as_of = resolve_as_of(as_of)
    try:
        result = f06_analysis(int(machine_id), as_of)
    except (OSError, ValueError, KeyError):
        return (f06_sensor_figure({}, sensor), html.Div("IF 결과 없음"),
                html.Div("센서 분석 자료를 읽지 못했습니다."),
                html.Span("이상 판정 불가", className="f06-summary-ok"),
                "관측 시점 미확정")
    observed = result.get("observed_at")
    observed_label = (f"센서 관측 {observed.replace('T', ' ')} · 기준일 {as_of}"
                      if observed else "해당 시점의 센서 관측 없음")
    if result.get("observation_age_hours", 0) > 0:
        observed_label += f" · 관측 후 {result['observation_age_hours']:g}시간 경과"
    return (f06_sensor_figure(result, sensor), f06_if_card(result),
            f06_reason_table(result), f06_alert_summary(result, sensor), observed_label)


@callback(
    Output("dt-sensor-count", "children"),
    Output("dt-sensor-spark", "figure"),
    Input("detail-machine-select", "value"),
    State("store-as-of", "data"),
)
def show_sensor_overview(machine_id, as_of):
    """캔버스용: 72시간 이상 건수(센서 4종 IQR·3σ + 설비 IF)와 시간별 건수 미리보기."""
    if machine_id not in MACHINES:
        raise PreventUpdate
    try:
        result = f06_analysis(int(machine_id), resolve_as_of(as_of))
    except (OSError, ValueError, KeyError):
        return "—", figure_base()
    points = result.get("timeline", [])

    def flags(point):
        sensors = point.get("sensors", {})
        count = sum(bool(row and row.get(method) and row[method]["is_anomaly"])
                    for row in sensors.values() for method in ("iqr", "three_sigma"))
        return count + bool(point.get("if") and point["if"]["is_anomaly"])

    per_hour = [flags(point) for point in points]
    figure = figure_base()
    figure.update_layout(margin={"l": 0, "r": 0, "t": 4, "b": 0}, bargap=0.25)
    figure.add_trace(go.Bar(x=[point["as_of"] for point in points], y=per_hour,
                            marker_color=[DANGER if value else "#c9d3df" for value in per_hour]))
    figure.update_xaxes(visible=False)
    figure.update_yaxes(visible=False, range=[0, max(per_hour or [1]) + 0.5])
    return [html.Strong(f"{sum(per_hour)}"), html.Span("건")], figure


# ---------------- ⑤ 발주 검토 ----------------
@callback(
    Output("f07-collapse", "is_open"),
    Output("store-selected-comp", "data"),
    Output("f07-part-label", "children"),
    [Input(f"hotspot-{c}", "n_clicks") for c in COMPS] +
    [Input("btn-f07-close", "n_clicks"),
     Input({"type": "dt-part-order", "comp": ALL}, "n_clicks")],
    prevent_initial_call=True,
)
def toggle_f07(*_):
    trig = ctx.triggered_id
    if trig == "btn-f07-close":
        return False, None, "--"
    if not ctx.triggered or not ctx.triggered[0]["value"]:
        raise PreventUpdate
    comp = trig["comp"] if isinstance(trig, dict) else str(trig).replace("hotspot-", "")
    return True, comp, f"— {comp} ({DECISION.get(comp, '-')}일 발주 결정 시한)"


@callback(
    Output("f07-cost-curve", "figure"),
    Output("f07-order-info", "children"),
    Output("f07-cost-d0", "children"),
    Output("f07-cost-d7", "children"),
    Output("f07-cost-d14", "children"),
    Input("store-selected-comp", "data"),
    State("store-selected-machine", "data"),
    State("store-as-of", "data"),
)
def show_f07(comp, machine_id, as_of):
    if comp not in COMPS:
        raise PreventUpdate
    as_of = resolve_as_of(as_of)
    part = next(part for part in part_rows(machine_id, as_of) if part["comp"] == comp)
    curve = detail_data.cost_curve(comp, part["days"] if part["adopted"] else None, as_of)

    figure = figure_base()
    figure.add_trace(go.Scatter(
        x=curve["dates"], y=curve["totals"], mode="lines", line={"color": NAVY, "width": 2.5, "shape": "spline"},
        fill="tozeroy", fillcolor="rgba(0,53,102,.07)",
        hovertemplate="%{x} 발주<br>예상 총비용 %{y:,.0f}만원<extra></extra>"))
    best = curve["best_day"]
    figure.add_trace(go.Scatter(
        x=[curve["dates"][best]], y=[curve["totals"][best]], mode="markers+text",
        marker={"size": 13, "color": YELLOW, "line": {"color": NAVY, "width": 2}},
        text=[f"최저 {curve['totals'][best]:,.0f}만원"], textposition="top right",
        textfont={"color": INK, "size": 12}, hoverinfo="skip"))
    figure.add_vline(x=curve["deadline"], line={"color": DANGER, "width": 1.5, "dash": "dot"},
                     annotation={"text": "발주 마감", "font": {"color": DANGER, "size": 11}},
                     annotation_position="top right")
    figure.update_xaxes(showgrid=False, tickformat="%m/%d", linecolor=GRID)
    figure.update_yaxes(gridcolor=GRID, zeroline=False, ticksuffix="만",
                        range=[0, max(curve["totals"]) * 1.2])

    warn = []
    if curve["too_late"]:
        warn = html.Div(f"조달에 {curve['lead']}일이 걸려 위험 상승({d_label(curve['rise'])}) 전에 받기 어렵습니다. "
                        "오늘 발주하거나 긴급 대체 업체를 검토하세요.", className="dt-warn")
    info = html.Div([
        html.Dl([
            html.Dt("발주 마감"), html.Dd(f"{curve['deadline']} (D-{curve['deadline_day']})",
                                        className="is-alert" if curve["deadline_day"] <= 3 else ""),
            html.Dt("권장 수량"), html.Dd(f"{curve['quantity']}개"),
            html.Dt("조달 기간"), html.Dd(f"{curve['lead']}일 (준비 포함)"),
            html.Dt("현재 재고"), html.Dd(f"{curve['stock']}개", className="is-alert" if not curve["stock"] else ""),
            html.Dt("대응 여유"), html.Dd(f"{curve['slack']}일"),
        ], className="dt-kv"),
        warn,
    ])
    scenario = curve["scenario"]
    lowest = min(scenario.values())

    def tile(day):
        value = scenario[day]
        return [won(value), html.Small("최저" if value == lowest else f"+{won(value - lowest)}",
                                       className="is-best" if value == lowest else "")]
    return figure, info, tile(0), tile(7), tile(14)


# ---------------- ⑤ 발주 정보 (장바구니) ----------------
@callback(
    Output("store-order-cart", "data", allow_duplicate=True),
    Input("btn-add-cart", "n_clicks"),
    Input({"type": "f08-remove", "key": ALL}, "n_clicks"),
    Input("f08-clear", "n_clicks"),
    State("store-selected-machine", "data"),
    State("store-selected-comp", "data"),
    State("store-order-cart", "data"),
    prevent_initial_call=True,
)
def update_cart(_add, _remove, _clear, machine_id, comp, cart):
    cart = list(cart or [])
    trig = ctx.triggered_id
    if not ctx.triggered or not ctx.triggered[0]["value"]:
        raise PreventUpdate
    if trig == "f08-clear":
        return []
    if isinstance(trig, dict):
        return [item for item in cart if item["key"] != trig["key"]]
    if comp not in COMPS:
        raise PreventUpdate
    key = f"{machine_id}-{comp}"
    if all(item["key"] != key for item in cart):
        cart.append({"key": key, "machine": machine_id, "comp": comp, "ordered": None})
    return cart


@callback(
    Output("f08-supplier-collapse", "is_open"),
    Input("btn-add-cart", "n_clicks"),
    Input("dt-cart-btn", "n_clicks"),
    Input("btn-f08-supplier-close", "n_clicks"),
    prevent_initial_call=True,
)
def toggle_supplier(*_):
    return ctx.triggered_id != "btn-f08-supplier-close"


@callback(
    Output("f08-supplier-body", "children"),
    Output("dt-cart-btn", "children"),
    Input("store-order-cart", "data"),
    State("store-as-of", "data"),
)
def render_cart(cart, as_of):
    cart = cart or []
    label = f"발주 정보 {len(cart)}건"
    if not cart:
        return ghost("발주 검토에서 '발주 정보 보기'를 누르면 부품별로 쌓입니다", 100), label
    as_of = resolve_as_of(as_of)
    cards = []
    for item in cart:
        part = next(part for part in part_rows(item["machine"], as_of) if part["comp"] == item["comp"])
        curve = detail_data.cost_curve(item["comp"], part["days"] if part["adopted"] else None, as_of)
        rows = []
        for supplier in detail_data.suppliers_for(item["comp"]):
            ordered = item.get("ordered") == supplier["id"]
            price = won(supplier["price"]) + (f" (할증 {won(supplier['surcharge'])})" if supplier["surcharge"] else "")
            rows.append(html.Tr([
                html.Td([html.B(supplier["name"]), html.Span(supplier["tag"], className="dt-sup-tag")]),
                html.Td(f"{supplier['lead']}일"),
                html.Td(price),
                html.Td(supplier["contact"]),
                html.Td(html.Span("발주 완료", className="dt-status dt-status--ok") if ordered else
                        html.Button("발주 요청", id={"type": "f08-order", "key": f"{item['key']}|{supplier['id']}"},
                                    className="dt-btn dt-btn--primary dt-btn--sm",
                                    disabled=bool(item.get("ordered")))),
            ], className="is-ordered" if ordered else ""))
        cards.append(html.Div(className="dt-cart-item", children=[
            html.Div([
                html.B(f"M-{item['machine']:03d} · {item['comp']}"),
                html.Span(f"발주 마감 {curve['deadline'][5:].replace('-', '/')} (D-{curve['deadline_day']}) · "
                          f"권장 {curve['quantity']}개 · 재고 {curve['stock']}개", className="dt-cart-meta"),
                html.Button("✕", id={"type": "f08-remove", "key": item["key"]}, className="dt-icon-btn",
                            title="목록에서 빼기", **{"aria-label": "목록에서 빼기"}),
            ], className="dt-cart-head"),
            html.Div(html.Table([html.Thead(html.Tr([html.Th(name) for name in ("업체", "납기", "단가", "연락처", "")])),
                                 html.Tbody(rows)], className="dt-table"), className="table-scroll"),
        ]))
    return html.Div(cards, className="dt-cart"), label


# TODO(기능): 실제 발주 시스템과 연결. 지금은 '발주 요청'을 누르면 세션에 기록만 한다.
@callback(
    Output("store-order-log", "data"),
    Output("store-order-cart", "data", allow_duplicate=True),
    Output("f08-last-order", "data"),
    Input({"type": "f08-order", "key": ALL}, "n_clicks"),
    State("store-order-log", "data"),
    State("store-order-cart", "data"),
    State("store-as-of", "data"),
    prevent_initial_call=True,
)
def place_order(_clicks, orders, cart, as_of):
    if not ctx.triggered or not ctx.triggered[0]["value"] or not isinstance(ctx.triggered_id, dict):
        raise PreventUpdate
    item_key, supplier = ctx.triggered_id["key"].split("|")
    item = next((item for item in cart or [] if item["key"] == item_key), None)
    if item is None:
        raise PreventUpdate
    cart = [{**row, "ordered": supplier} if row["key"] == item_key else row for row in cart]
    order = {"machine": item["machine"], "component": item["comp"], "supplier": supplier,
             "date": valid_as_of(as_of)}
    return [*(orders or []), order], cart, order


@callback(
    Output("f08-history-table", "children"),
    Input("detail-machine-select", "value"),
    State("store-as-of", "data"),
)
def show_history(machine_id, as_of):
    """교체 이력: 부품별 타임라인(원본 정비 기록) + 최근 기록 표."""
    history = detail_data.replacement_history(machine_id, resolve_as_of(as_of))
    rows = history["rows"]
    figure = figure_base()
    for failure, name, color, symbol in ((False, "예방 교체", NAVY, "circle"), (True, "고장 후 교체", DANGER, "x")):
        part = [row for row in rows if row["failure"] == failure]
        figure.add_trace(go.Scatter(
            x=[row["date"] for row in part], y=[row["comp"] for row in part], mode="markers", name=name,
            marker={"size": 13, "color": color, "symbol": symbol, "line": {"color": "white", "width": 2}},
            customdata=[[row["cost"]] for row in part],
            hovertemplate=f"%{{x}} · %{{y}}<br>{name} · %{{customdata[0]:,}}만원<extra></extra>"))
    figure.update_layout(showlegend=True, legend={"orientation": "h", "x": 1, "xanchor": "right", "y": 1.18,
                                                  "font": {"color": INK}},
                         margin={"l": 8, "r": 12, "t": 28, "b": 8})
    figure.update_xaxes(range=[history["start"], history["end"]], showgrid=True, gridcolor=GRID,
                        tickformat="%y.%m", linecolor=GRID)
    figure.update_yaxes(categoryorder="array", categoryarray=list(reversed(COMPS)), gridcolor=GRID)
    table = html.Table([
        html.Thead(html.Tr([html.Th(name) for name in ("교체일", "부품", "구분", "담당자", "비용")])),
        html.Tbody([html.Tr([
            html.Td(row["date"]), html.Td(row["comp"]),
            html.Td(html.Span("고장 후 교체" if row["failure"] else "예방 교체",
                              className="dt-status dt-status--now" if row["failure"] else "dt-status dt-status--ok")),
            html.Td(row["worker"]), html.Td(won(row["cost"])),
        ]) for row in rows[:8]]),
    ], className="dt-table")
    failures = sum(row["failure"] for row in rows)
    return html.Div(className="dt-history", children=[
        html.Div([
            html.H3(f"최근 12개월 교체 {len(rows)}건 · 고장 후 교체 {failures}건"),
            dcc.Graph(figure=figure, config={"displayModeBar": False}, responsive=True,
                      style={"height": "clamp(200px,24vh,260px)"}),
        ], className="dt-f07-block"),
        html.Div([html.H3("최근 기록"), html.Div(table, className="table-scroll")], className="dt-f07-block"),
    ])


@callback(
    Output("f08-history-collapse", "is_open"),
    Input("btn-open-history", "n_clicks"),
    Input("btn-f08-history-close", "n_clicks"),
    prevent_initial_call=True,
)
def toggle_history(*_):
    return ctx.triggered_id == "btn-open-history"


# ---------------- 발주 → 메인 TOP5에서 삭제 확인 ----------------
def top5_matches(machine_id, comp, dismissed, as_of=UI_AS_OF):
    """발주한 설비(·부품)가 메인 TOP5에 있으면 그 항목들을 반환."""
    top = ranked_items(dismissed, as_of=valid_as_of(as_of))[:5]
    return [item for item in top if item["machine"] == machine_id
            and (comp is None or item.get("component") in (None, comp))]


@callback(
    Output("f07-confirm-dismiss", "displayed"),
    Output("f07-confirm-dismiss", "message"),
    Input("f08-last-order", "data"),
    State("store-todo-dismissed", "data"),
    State("store-as-of", "data"),
    prevent_initial_call=True,
)
def ask_dismiss(order, dismissed, as_of):
    if not order or not top5_matches(order["machine"], order["component"], dismissed, as_of):
        raise PreventUpdate
    label = f"M-{order['machine']:03d} {order['component']}"
    return True, (f"{label} 발주를 요청했습니다. 이 항목이 메인 화면 '우선 확인 설비 TOP5'에 있습니다.\n"
                  "우선순위에서 삭제하시겠습니까?")


@callback(
    Output("store-todo-dismissed", "data", allow_duplicate=True),
    Input("f07-confirm-dismiss", "submit_n_clicks"),
    State("f08-last-order", "data"),
    State("store-todo-dismissed", "data"),
    State("store-as-of", "data"),
    prevent_initial_call=True,
)
def dismiss_ordered(submitted, order, dismissed, as_of):
    matches = top5_matches(order["machine"], order["component"], dismissed, as_of) if order else []
    if not submitted or not matches:
        raise PreventUpdate
    return list(dict.fromkeys([*(dismissed or []), *(item["key"] for item in matches)]))
