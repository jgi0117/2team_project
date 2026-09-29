# src/ui/pages/detail.py
# 설비 상세 페이지 - 프레임(빈 박스 + id + 펼침/접힘) / 반응형
from dash import html, dcc, Input, Output, State, callback, ctx
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from src.F09.heatmap import load_predictions, machine_ids
from src.ui.ai_data import f05_diagnosis, f06_analysis
from src.F07 import analyze_order
from src.F08 import get_history, get_supplier
from src.ui.config import UI_AS_OF

PREDICTIONS = load_predictions()
MACHINES = machine_ids()
AS_OF = UI_AS_OF
MODEL_VERSION = sorted(PREDICTIONS.loc[PREDICTIONS.as_of.eq(AS_OF), "model_version"].unique())[-1]

COMPS    = ["comp1", "comp2", "comp3", "comp4"]
DECISION = {"comp1": 8, "comp2": 42, "comp3": 16, "comp4": 24}
ADOPTED  = {"comp1": True, "comp2": False, "comp3": True, "comp4": True}
SENSOR_NAMES = {"volt": "전압", "rotate": "회전속도", "pressure": "압력", "vibration": "진동"}

# 설비 이미지 위 부품 좌표(%) — 이미지 바뀌면 이 숫자만 수정
POS = {
    "comp1": {"top": "16%", "left": "22%"},
    "comp2": {"top": "26%", "left": "62%"},
    "comp3": {"top": "58%", "left": "32%"},
    "comp4": {"top": "68%", "left": "72%"},
}


def ghost(text, min_h=80):
    return html.Div(text, className="ghost", style={"minHeight": f"{min_h}px"})


# ---------------- F05 : 부품 말풍선 ----------------
def hotspot(comp):
    on = ADOPTED[comp]
    color = "#c62828" if on else "#9aa5b1"

    dot = html.Div(className="hotspot-dot",
                   style={**POS[comp], "background": color})

    bubble = html.Div(
        id=f"hotspot-{comp}", n_clicks=0, className="hotspot",
        style={**POS[comp], "border": f"1px solid {color}",
               "borderLeft": f"4px solid {color}"},
        children=[
            html.Div([
                html.Span(comp, id=f"hs-name-{comp}", style={"fontWeight": 700}),
                html.Span(f" | {DECISION[comp]}일", id=f"hs-horizon-{comp}",
                          style={"color": "#667"}),
            ]),
            html.Div("--", id=f"hs-prob-{comp}",
                     className="hotspot-prob", style={"color": color}),
            html.Div("" if on else "미채택(안전재고)", className="hs-note",
                     style={"fontSize": "10px", "color": "#9aa5b1"}),
        ],
    )

    return [dot, bubble]


# ---------------- F06 : 겹치는 오버레이 ----------------
f06_overlay = html.Div(
    id="f06-overlay", className="box f06-layer",
    children=[
        html.Div([html.Span("센서 이상 추이 및 판단 근거", style={"fontWeight": 700}),
                  dcc.Dropdown(
                      id="f06-sensor-select",
                      options=[{"label": f"{label} ({sensor})", "value": sensor}
                               for sensor, label in SENSOR_NAMES.items()],
                      value="vibration", clearable=False,
                      className="f06-sensor-select",
                  )],
                 className="panel-hdr"),
        html.Small(id="f06-observed", className="f06-observed"),
        html.Small("선택 센서의 관측값·기준 범위와 설비 전체 IF 점수", className="f06-observed"),
        html.Div(id="f06-alert-summary", className="f06-alert-summary"),
        dcc.Graph(id="f06-sensor-graph", figure={}, responsive=True,
                  config={"displayModeBar": False},
                  style={"height": "clamp(260px,37vh,340px)"}),
        html.Small("파랑 센서값·IF 점수 · 보라 IQR UDL/LDL(탐지 상·하한) · 주황 3σ UCL/LCL(관리 상·하한) · 빨강 이상",
                   className="f06-observed"),
        html.Div(className="f06-row", children=[
            html.Div(id="f06-if-score", children=ghost("IF 점수", 84), className="f06-gauge"),
            html.Div(html.Div(id="f06-reason-table",
                              children=ghost("센서별 판정", 84)),
                     className="f06-reason"),
        ]),
    ],
)

# ---------------- F05 : 좌상단 종합 진단 ----------------
f05_summary = html.Div(
    id="f05-summary", className="box summary-card",
    children=[
        html.Div([html.Span("현재 설비 상태",
                           style={"fontWeight": 700, "fontSize": "13px"})],
                 style={"display": "flex", "gap": "6px", "alignItems": "center"}),
        html.Div("진단 불러오는 중", id="f05-summary-days", className="summary-days"),
        html.Div("동일 기간 부품 위험 비교", id="f05-summary-note", className="summary-sub"),
        html.Div("Qwen 종합진단을 준비하고 있습니다", id="f05-summary-basis", className="summary-sub"),
    ],
)

# ---------------- F05 무대 ----------------
f05_stage = html.Div(className="stage", children=[
    html.Div(className="stage-canvas", children=[
        html.Div(id="f05-equip-img", className="stage-bg",
                 children=html.Img(
                     src="/assets/equipment-comp-layout.png",
                     alt="4개 부품 위치가 표시된 산업용 설비",
                 )),
        f05_summary,
        *[el for c in COMPS for el in hotspot(c)],
        html.Div(className="stage-actions", children=[
            dbc.Button("교체 이력 보기", id="btn-open-history",
                       size="sm", color="secondary", outline=True, n_clicks=0),
        ]),
    ]),
    f06_overlay,          # 넓으면 위에 겹침 / 좁으면 CSS가 아래로 내림
])

# ---------------- F07 ----------------
f07_panel = dbc.Collapse(
    id="f07-collapse", is_open=False,
    children=html.Div(className="box",
                      style={"marginTop": "14px", "borderTop": "3px solid #ef6c00"},
                      children=[
        html.Div(className="panel-hdr", children=[
            html.Span("발주 시점 및 비용 비교 —", style={"fontWeight": 700}),
            html.Span("--", id="f07-part-label",
                      style={"fontWeight": 700, "color": "#ef6c00"}),
            html.Div(className="btns", children=[
                dbc.Button("협력사 확인", id="btn-add-cart", size="sm",
                           color="primary", n_clicks=0),
                dbc.Button("닫기", id="btn-f07-close", size="sm",
                           color="light", n_clicks=0),
            ]),
        ]),
        dbc.Row(className="g-2", children=[
            dbc.Col(md=12, lg=5, children=html.Div(className="box", children=[
                html.Div("비용 최소 발주 시점",
                         style={"fontWeight": 700, "fontSize": "13px"}),
                dcc.Graph(id="f07-cost-curve", figure={}, responsive=True,
                          config={"displayModeBar": False},
                          style={"height": "clamp(140px,20vh,190px)"}),
            ])),
            dbc.Col(md=6, lg=3, children=html.Div(className="box", children=[
                html.Div("발주 및 재고 정보",
                         style={"fontWeight": 700, "fontSize": "13px",
                                "marginBottom": "6px"}),
                html.Div(id="f07-order-info",
                         children=ghost("발주마감일 / 권장수량 / 조달기간 / 대응여유", 150)),
            ])),
            dbc.Col(md=6, lg=4, children=html.Div(className="box", children=[
                html.Div("시나리오 비교",
                         style={"fontWeight": 700, "fontSize": "13px",
                                "marginBottom": "6px"}),
                dbc.Row(className="g-2", children=[
                    dbc.Col(xs=12, sm=4, children=html.Div(className="box",
                        style={"textAlign": "center", "fontSize": "12px"},
                        children=["오늘 발주", html.Div("--", id="f07-cost-d0",
                                                     style={"fontWeight": 700})])),
                    dbc.Col(xs=12, sm=4, children=html.Div(className="box",
                        style={"textAlign": "center", "fontSize": "12px"},
                        children=["1주 대기", html.Div("--", id="f07-cost-d7",
                                                     style={"fontWeight": 700})])),
                    dbc.Col(xs=12, sm=4, children=html.Div(className="box",
                        style={"textAlign": "center", "fontSize": "12px"},
                        children=["2주 대기", html.Div("--", id="f07-cost-d14",
                                                      style={"fontWeight": 700})])),
                ]),
            ])),
        ]),
    ]),
)

# ---------------- F08-a : 협력사 ----------------
f08_supplier = dbc.Collapse(
    id="f08-supplier-collapse", is_open=False,
    children=html.Div(className="box",
                      style={"marginTop": "12px", "borderTop": "3px solid #2e7d32"},
                      children=[
        html.Div(className="panel-hdr", children=[
            html.Span("부품 조달처 및 담당자", style={"fontWeight": 700}),
            html.Div(className="btns", children=[
                dbc.Button("닫기", id="btn-f08-supplier-close",
                           size="sm", color="light", n_clicks=0)]),
        ]),
        html.Div(id="f08-supplier-body",
                 children=ghost("업체명 / 재고 / 납기 / 단가 / 연락처", 100)),
    ]),
)

# ---------------- F08-b : 교체 이력 ----------------
f08_history = dbc.Collapse(
    id="f08-history-collapse", is_open=False,
    children=html.Div(className="box",
                      style={"marginTop": "12px", "borderTop": "3px solid #2e7d32"},
                      children=[
        html.Div(className="panel-hdr", children=[
            html.Span("정비·조치 이력", style={"fontWeight": 700}),
            html.Div(className="btns", children=[
                dbc.Button("닫기", id="btn-f08-history-close",
                           size="sm", color="light", n_clicks=0)]),
        ]),
        dbc.Row(className="g-2 f08-action-form", children=[
            dbc.Col(md=3, children=dcc.Dropdown(
                id="f08-action-status", clearable=False, value="확인",
                options=[{"label": value, "value": value}
                         for value in ["확인", "발주 요청", "점검 완료", "조치 보류"]])),
            dbc.Col(md=7, children=dbc.Input(id="f08-action-note", placeholder="조치 내용 또는 담당자 메모")),
            dbc.Col(md=2, children=dbc.Button("기록", id="btn-record-action", color="success",
                                              className="w-100", n_clicks=0)),
        ]),
        html.Div(id="f08-history-table", style={"overflowX": "auto", "marginTop": "10px"},
                 children=ghost("교체일 / 부품 / 처리 결과 / 조치 메모", 130)),
        html.Div([
            dbc.Button("‹", id="btn-history-prev", color="light", size="sm", n_clicks=0),
            html.Span("1 / 1", id="f08-history-page-label"),
            dbc.Button("›", id="btn-history-next", color="light", size="sm", n_clicks=0),
        ], className="f08-pagination"),
    ]),
)

# ---------------- layout ----------------
def create_detail_layout(machine_id=None):
    selected = machine_id if machine_id in MACHINES else MACHINES[0]
    return html.Div(className="page-detail", children=[
        dcc.Store(id="store-selected-machine", data=selected),
        dcc.Store(id="store-selected-comp", data=None),
        dcc.Store(id="store-action-log", data=[], storage_type="local"),
        dcc.Store(id="store-history-page", data=0),

        html.Div(className="hdr", children=[
            html.Span("설비 상세 —", style={"fontSize": "clamp(15px,1.6vw,18px)",
                                           "fontWeight": 700}),
            html.Span(f"M-{selected:03d}", id="detail-machine-name",
                      style={"fontSize": "clamp(15px,1.6vw,18px)", "fontWeight": 800}),
            dcc.Dropdown(
                id="detail-machine-select",
                options=[{"label": f"M-{machine:03d}", "value": machine} for machine in MACHINES],
                value=selected, clearable=False,
                className="detail-machine-select",
            ),
            html.Span(f"기준일 {AS_OF}", id="detail-asof", className="hdr-right",
                      style={"fontSize": "12px", "color": "#667"}),
        ]),
        html.P(
            "부품별 고장 예측과 센서 이상은 서로 다른 결과입니다. 발주 판단은 해당 시점의 재고·입고 예정·조달기간과 합성 비용 조건을 사용합니다.",
            className="detail-frame-note",
        ),

        f05_stage,
        f07_panel,
        f08_supplier,
        f08_history,
    ])


layout = create_detail_layout()


@callback(
    Output("detail-machine-name", "children"),
    Output("store-selected-machine", "data"),
    *[Output(f"hs-prob-{comp}", "children") for comp in COMPS],
    Output("f05-summary-days", "children"),
    Output("f05-summary-note", "children"),
    Output("f05-summary-basis", "children"),
    Input("detail-machine-select", "value"),
)
def show_machine(machine_id):
    rows = PREDICTIONS.loc[
        PREDICTIONS.as_of.eq(AS_OF)
        & PREDICTIONS.model_version.eq(MODEL_VERSION)
        & PREDICTIONS.machineID.eq(machine_id)
    ]
    scores = []
    for comp in COMPS:
        selected = rows.loc[
            rows.component.eq(comp) & rows.horizon_days.eq(DECISION[comp]),
        ]
        if selected.empty or selected.failure_probability.isna().all():
            scores.append("--")
        else:
            row = selected.iloc[0]
            scores.append(f"{row.failure_probability:.1%}" if row.calibrated
                          else f"{row.failure_probability:.3f}")
    try:
        diagnosis = f05_diagnosis(int(machine_id), AS_OF)
    except (OSError, ValueError, KeyError):
        summary = ("진단 불가", "예측 자료 확인 필요", "종합진단 자료를 읽지 못했습니다")
    else:
        if diagnosis["status"] == "no_data":
            summary = (html.Span("판정 불가", className="diagnosis-watch"),
                       "예측 자료 확인 필요", diagnosis["text"])
        else:
            state = diagnosis.get("condition_status", "watch")
            labels = {"normal": "현재 정상", "watch": "관찰 필요", "priority": "우선 점검 필요"}
            rank = int(diagnosis.get("risk_rank", 0))
            population = int(diagnosis.get("risk_population", len(MACHINES)))
            notes = {
                "normal": "센서 경고 없음 · 동일 조건 설비 대비 정상 범위",
                "watch": f"센서 또는 위험도 변화 관찰 · 위험 순위 {rank}/{population}",
                "priority": ("센서 이상 경고 감지" if diagnosis.get("anomaly_detected") else
                             f"동일 조건 설비 대비 높은 위험 · 위험 순위 {rank}/{population}"),
            }
            summary = (html.Span(labels[state], className=f"diagnosis-{state}"),
                       f"향후 {diagnosis['horizon_days']}일 고장예측·현재 센서 종합",
                       f"근거: {notes[state]}")
    return f"M-{machine_id:03d}", machine_id, *scores, *summary


def f06_sensor_figure(result, sensor):
    if sensor not in SENSOR_NAMES:
        sensor = "vibration"
    figure = make_subplots(rows=2, cols=1, shared_xaxes=True,
                           row_heights=[.68, .32], vertical_spacing=.12)
    points = result.get("timeline", [])
    if not points:
        figure.add_annotation(text="시간별 관측 없음", x=0.5, y=0.5, xref="paper", yref="paper",
                              showarrow=False)
    else:
        x = [point["as_of"] for point in points]
        rows = [point.get("sensors", {}).get(sensor) for point in points]
        values = [None if row is None else row["value"] for row in rows]
        figure.add_trace(go.Scatter(x=x, y=values, mode="lines+markers", name=SENSOR_NAMES[sensor],
                                    line={"color": "#1976d2", "width": 2},
                                    marker={"size": 4}, connectgaps=False), row=1, col=1)
        for method, label, color, limits in (("iqr", "IQR", "#7c3aed", ("UDL", "LDL")),
                                             ("three_sigma", "3σ", "#d97706", ("UCL", "LCL"))):
            decisions = [None if row is None else row.get(method) for row in rows]
            for (bound, dash), limit_name in zip((("upper", "dash"), ("lower", "dot")), limits):
                figure.add_trace(go.Scatter(
                    x=x, y=[None if item is None else item[bound] for item in decisions],
                    mode="lines", name=f"{label} {limit_name}",
                    line={"color": color, "width": 1, "dash": dash}, connectgaps=False,
                    hovertemplate=f"%{{x}}<br>{label} {limit_name}: %{{y:.3f}}<extra></extra>",
                ), row=1, col=1)
            flagged = [(time, value) for time, value, item in zip(x, values, decisions)
                       if value is not None and item is not None and item["is_anomaly"]]
            figure.add_trace(go.Scatter(
                x=[item[0] for item in flagged], y=[item[1] for item in flagged],
                mode="markers", name=f"{label} 이상",
                marker={"color": "#c62828", "size": 12,
                        "symbol": "x" if method == "iqr" else "diamond"},
                hovertemplate=f"%{{x}}<br>{label} 이상: %{{y:.3f}}<extra></extra>",
            ), row=1, col=1)
        if_results = [point.get("if") for point in points]
        figure.add_trace(go.Scatter(
            x=x, y=[None if item is None else item["anomaly_score"] for item in if_results],
            mode="lines+markers", name="IF 점수", line={"color": "#1976d2", "width": 2},
            marker={"size": 4}, connectgaps=False,
        ), row=2, col=1)
        figure.add_trace(go.Scatter(
            x=x, y=[None if item is None else item["threshold"] for item in if_results],
            mode="lines", name="IF 기준", line={"color": "#d97706", "width": 1, "dash": "dash"},
            connectgaps=False,
        ), row=2, col=1)
        flagged_if = [(time, item["anomaly_score"]) for time, item in zip(x, if_results)
                      if item is not None and item["is_anomaly"]]
        figure.add_trace(go.Scatter(
            x=[item[0] for item in flagged_if], y=[item[1] for item in flagged_if],
            mode="markers", name="IF 이상",
            marker={"color": "#c62828", "size": 11, "line": {"color": "white", "width": 1}},
        ), row=2, col=1)
    figure.update_layout(
        margin={"l": 42, "r": 8, "t": 8, "b": 30}, showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font={"size": 10, "color": "#526579"},
    )
    figure.update_xaxes(showgrid=False, tickformat="%m-%d %H:%M", nticks=3)
    figure.update_yaxes(gridcolor="#e5e9ef", title_text=SENSOR_NAMES[sensor], row=1, col=1)
    figure.update_yaxes(gridcolor="#e5e9ef", title_text="IF", row=2, col=1)
    return figure


def f06_if_card(result):
    score = result.get("if")
    if score is None:
        return html.Div([html.Small("IF 이상 점수"), html.Strong("결과 없음"),
                         html.Small("같은 시점의 결과 미제공")], className="f06-if-card")
    return html.Div([
        html.Small("IF 이상 점수"),
        html.Strong(f"{score['anomaly_score']:.3f}"),
        html.Small(f"경고 기준 > {score['threshold']:.3f}"),
        html.Small("경고" if score["is_anomaly"] else "경고 없음",
                   className="f06-if-alert" if score["is_anomaly"] else ""),
        html.Small("확률 아님"),
    ], className="f06-if-card")


def f06_reason_table(result):
    if not result.get("sensors"):
        return html.Div("센서 결과 없음", className="f06-empty")

    def decision(bounds):
        if bounds is None:
            return html.Td("미확정", className="f06-undetermined")
        label = "이탈" if bounds["is_anomaly"] else "범위 내"
        return html.Td(label, className="f06-alert" if bounds["is_anomaly"] else "",
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


def f06_alert_summary(result, sensor):
    if sensor not in SENSOR_NAMES:
        sensor = "vibration"
    points = result.get("timeline", [])
    if not points:
        return html.Span("표시할 센서 관측이 없습니다")
    counts, available = {}, {}
    for method in ("iqr", "three_sigma", "if"):
        decisions = [point.get("if") if method == "if" else
                     point.get("sensors", {}).get(sensor, {}).get(method) for point in points]
        counts[method] = sum(bool(item and item["is_anomaly"]) for item in decisions)
        available[method] = sum(item is not None for item in decisions)
    total = sum(counts.values())
    state = ("이상 없음" if all(available.values()) and not total else
             "판정 가능 시점에서 이상 없음" if not total else "이상 신호 있음")
    label = (f"최근 {result.get('window_hours', 72)}시간 · 선택 센서 IQR {counts['iqr']}건, "
             f"3σ {counts['three_sigma']}건 · 설비 IF {counts['if']}건 · {state}")
    return html.Span(label, style={"color": "#b42318" if total else "#526579"})


@callback(
    Output("f06-sensor-graph", "figure"),
    Output("f06-if-score", "children"),
    Output("f06-reason-table", "children"),
    Output("f06-alert-summary", "children"),
    Output("f06-observed", "children"),
    Input("detail-machine-select", "value"),
    Input("f06-sensor-select", "value"),
)
def show_f06(machine_id, sensor):
    if machine_id not in MACHINES:
        raise PreventUpdate
    try:
        result = f06_analysis(int(machine_id), AS_OF)
    except (OSError, ValueError, KeyError):
        return (f06_sensor_figure({}, sensor), html.Div("IF 결과 없음"),
                html.Div("센서 분석 자료를 읽지 못했습니다."),
                html.Span("이상 판정 불가"),
                "관측 시점 미확정")
    observed = result.get("observed_at")
    observed_label = (f"센서 관측 {observed.replace('T', ' ')} · 예측 기준 {AS_OF}"
                      if observed else "해당 시점의 센서 관측 없음")
    if result.get("observation_age_hours", 0) > 0:
        observed_label += f" · 관측 후 {result['observation_age_hours']:g}시간 경과"
    return (f06_sensor_figure(result, sensor), f06_if_card(result),
            f06_reason_table(result), f06_alert_summary(result, sensor), observed_label)


# ---------------- 프레임 콜백 (열림/닫힘만) ----------------
@callback(
    Output("f07-collapse", "is_open"),
    Output("store-selected-comp", "data"),
    Output("f07-part-label", "children"),
    [Input(f"hotspot-{c}", "n_clicks") for c in COMPS] +
    [Input("btn-f07-close", "n_clicks")],
    prevent_initial_call=True,
)
def toggle_f07(*_):
    trig = ctx.triggered_id
    if trig == "btn-f07-close":
        return False, None, "--"
    comp = str(trig).replace("hotspot-", "")
    return True, comp, f"{comp} ({DECISION.get(comp, '-')}일 기준)"


@callback(
    Output("f08-supplier-collapse", "is_open"),
    Input("btn-add-cart", "n_clicks"),
    Input("btn-f08-supplier-close", "n_clicks"),
    prevent_initial_call=True,
)
def toggle_supplier(*_):
    return ctx.triggered_id == "btn-add-cart"


@callback(
    Output("f08-history-collapse", "is_open"),
    Input("btn-open-history", "n_clicks"),
    Input("btn-f08-history-close", "n_clicks"),
    prevent_initial_call=True,
)
def toggle_history(*_):
    return ctx.triggered_id == "btn-open-history"


def _krw(value):
    value = float(value)
    return f"{value / 10_000:,.0f}만원" if abs(value) >= 10_000 else f"{value:,.0f}원"


@callback(
    Output("f07-cost-curve", "figure"),
    Output("f07-order-info", "children"),
    Output("f07-cost-d0", "children"),
    Output("f07-cost-d7", "children"),
    Output("f07-cost-d14", "children"),
    Input("store-selected-machine", "data"),
    Input("store-selected-comp", "data"),
)
def show_f07(machine_id, component):
    if not component:
        return go.Figure(), html.Div("부품을 선택하세요"), "--", "--", "--"
    result = analyze_order(int(machine_id), component, AS_OF)
    curve = result["curve"]
    optimum = result["optimum"]
    figure = go.Figure()
    figure.add_trace(go.Scatter(
        x=[row["delay_days"] for row in curve], y=[row["total_cost"] for row in curve],
        mode="lines", name="시나리오 비용", line={"color": "#2563eb", "width": 3},
        hovertemplate="%{x}일 후 발주<br>%{y:,.0f}원<extra></extra>",
    ))
    figure.add_trace(go.Scatter(
        x=[optimum["delay_days"]], y=[optimum["total_cost"]], mode="markers+text",
        text=["최소"], textposition="top center", name="비용 최소",
        marker={"color": "#dc2626", "size": 11},
    ))
    figure.update_layout(margin={"l": 55, "r": 10, "t": 18, "b": 35},
                         xaxis_title="기준일 이후 발주 지연(일)", yaxis_title="비용(원)",
                         showlegend=False, paper_bgcolor="rgba(0,0,0,0)",
                         plot_bgcolor="rgba(0,0,0,0)")
    plan = result["plan"]
    order_info = html.Dl([
        html.Dt("비용 최소 발주"), html.Dd(f"기준일 +{optimum['delay_days']}일"),
        html.Dt("계획 정비일"), html.Dd(str(pd.Timestamp(plan["target_maintenance_at"]).date())),
        html.Dt("발주 마감일"), html.Dd(str(pd.Timestamp(plan["order_by_at"]).date())),
        html.Dt("권장 수량"), html.Dd(f"{result['quantity']}개"),
        html.Dt("현재 가용재고"), html.Dd(f"{int(plan['available_stock'])}개"),
        html.Dt("대응 여유"), html.Dd(f"{int(plan['response_margin_days'])}일"),
        html.Dt("판단"), html.Dd(plan["reason"]),
    ], className="f07-order-list")
    return (figure, order_info, _krw(result["scenarios"][0]["total_cost"]),
            _krw(result["scenarios"][7]["total_cost"]), _krw(result["scenarios"][14]["total_cost"]))


@callback(Output("f08-supplier-body", "children"), Input("store-selected-comp", "data"))
def show_supplier(component):
    if not component:
        return html.Div("설비 이미지에서 부품을 선택하세요")
    info = get_supplier(component, AS_OF)
    return html.Div([
        html.Div([html.Strong(info["supplier_name"]), html.Span(f"{info['component']} · {info['part_name']}")],
                 className="f08-supplier-title"),
        html.Table(html.Tbody([
            html.Tr([html.Th("담당 부서"), html.Td(info["contact_department"])]),
            html.Tr([html.Th("전화"), html.Td(info["contact_phone"])]),
            html.Tr([html.Th("이메일"), html.Td(info["contact_email"])]),
            html.Tr([html.Th("가용재고 / 목표"), html.Td(f"{info['available_stock']}개 / {info['target_stock']}개")]),
            html.Tr([html.Th("표준 조달기간"), html.Td(f"{info['lead_time_days']}일")]),
        ]), className="f08-info-table"),
    ])


def _history_table(machine_id, local_actions, page=0, page_size=10):
    history = get_history(int(machine_id), AS_OF, limit=None)
    entries = [{"date": item["recorded_at"], "component": item.get("component", "—"),
                "result": item["status"], "detail": item.get("note") or "—", "user": True}
               for item in reversed(local_actions or [])
               if int(item.get("machineID", -1)) == int(machine_id)]
    entries.extend({
        "date": pd.Timestamp(row.planned_at).strftime("%Y-%m-%d"),
        "component": row.component,
        "result": "완료" if pd.notna(row.completed_at) else "대기",
        "detail": "—" if pd.isna(row.delay_days) else f"처리 {row.delay_days:g}일",
        "user": False,
    } for row in history.itertuples(index=False))
    total_pages = max(1, (len(entries) + page_size - 1) // page_size)
    page = min(max(0, int(page)), total_pages - 1)
    visible = entries[page * page_size:(page + 1) * page_size]
    table = html.Table([
        html.Thead(html.Tr([html.Th("일자"), html.Th("부품"), html.Th("결과/조치"),
                            html.Th("처리기간/메모")])),
        html.Tbody([html.Tr([
            html.Td(item["date"]), html.Td(item["component"]), html.Td(item["result"]),
            html.Td(item["detail"]),
        ], className="f08-user-action" if item["user"] else "") for item in visible]),
    ], className="f08-info-table")
    return table, page, total_pages, len(entries)


@callback(
    Output("f08-history-table", "children"),
    Output("store-action-log", "data"),
    Output("store-history-page", "data"),
    Output("f08-history-page-label", "children"),
    Output("btn-history-prev", "disabled"),
    Output("btn-history-next", "disabled"),
    Input("store-selected-machine", "data"),
    Input("btn-record-action", "n_clicks"),
    Input("btn-history-prev", "n_clicks"),
    Input("btn-history-next", "n_clicks"),
    State("store-selected-comp", "data"),
    State("f08-action-status", "value"),
    State("f08-action-note", "value"),
    State("store-action-log", "data"),
    State("store-history-page", "data"),
)
def show_history(machine_id, record_clicks, prev_clicks, next_clicks,
                 component, status, note, actions, page):
    actions = list(actions or [])
    page = int(page or 0)
    if ctx.triggered_id == "btn-record-action" and record_clicks:
        actions.append({"machineID": int(machine_id), "component": component,
                        "status": status or "확인", "note": (note or "").strip(),
                        "recorded_at": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")})
        page = 0
    elif ctx.triggered_id == "btn-history-prev":
        page -= 1
    elif ctx.triggered_id == "btn-history-next":
        page += 1
    elif ctx.triggered_id == "store-selected-machine":
        page = 0
    table, page, total_pages, total = _history_table(machine_id, actions, page)
    return table, actions, page, f"{page + 1} / {total_pages} · 전체 {total}건", page == 0, page >= total_pages - 1
