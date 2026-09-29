# src/ui/pages/detail.py
# 설비 상세 페이지 - 프레임(빈 박스 + id + 펼침/접힘) / 반응형
from dash import html, dcc, Input, Output, callback, ctx
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from src.F09.heatmap import load_predictions, machine_ids
from src.ui.ai_data import f05_diagnosis, f06_analysis
from src.ui.config import upto_as_of

PREDICTIONS = load_predictions()
MACHINES = machine_ids()
AS_OF = upto_as_of(PREDICTIONS).as_of.max()
MODEL_VERSION = sorted(PREDICTIONS.loc[PREDICTIONS.as_of.eq(AS_OF), "model_version"].unique())[-1]

COMPS    = ["comp1", "comp2", "comp3", "comp4"]
DECISION = {"comp1": 8, "comp2": 42, "comp3": 16, "comp4": 24}
ADOPTED  = {"comp1": True, "comp2": False, "comp3": True, "comp4": True}
HORIZONS = [7, 8, 14, 16, 21, 24, 28, 35, 42]
SENSOR_NAMES = {"volt": "전압", "rotate": "회전속도", "pressure": "압력", "vibration": "진동"}

# 설비 이미지 위 부품 좌표(%) — 이미지 바뀌면 이 숫자만 수정
POS = {
    "comp1": {"top": "16%", "left": "22%"},
    "comp2": {"top": "26%", "left": "62%"},
    "comp3": {"top": "58%", "left": "32%"},
    "comp4": {"top": "68%", "left": "72%"},
}


def tag(code):
    return html.Span(code, className=f"ftag ftag--{code.lower()}")


def ghost(text, min_h=80):
    return html.Div(text, className="ghost", style={"minHeight": f"{min_h}px"})


# ---------------- F05 : 부품 말풍선 ----------------
def hotspot(comp):
    on = ADOPTED[comp]
    state = "hotspot--on" if on else "hotspot--off"

    dot = html.Div(className=f"hotspot-dot {state}", style=POS[comp])

    bubble = html.Div(
        id=f"hotspot-{comp}", n_clicks=0, className=f"hotspot {state}",
        style=POS[comp],
        children=[
            html.Div([
                html.Span(comp, id=f"hs-name-{comp}", className="hs-name"),
                html.Span(f" | {DECISION[comp]}일", id=f"hs-horizon-{comp}",
                          className="hs-horizon"),
            ]),
            html.Div("--", id=f"hs-prob-{comp}", className="hotspot-prob"),
            html.Div("" if on else "안전재고 대응", className="hs-note"),
        ],
    )

    pop = dbc.Popover(
        [dbc.PopoverHeader(f"{comp} 기간별 고장 위험 점수"),
         dbc.PopoverBody(
             html.Div(className="pop-scroll", children=html.Div(
                 id=f"hs-pop-table-{comp}",
                 children=html.Table([
                     html.Thead(html.Tr([html.Th("기간")] +
                                        [html.Th(f"{h}일") for h in HORIZONS])),
                     html.Tbody(html.Tr([html.Td("점수")] +
                                        [html.Td("--") for _ in HORIZONS])),
                 ], className="hs-pop-table"))))],
        id=f"hs-pop-{comp}", target=f"hotspot-{comp}",
        trigger="hover", placement="auto",
    )
    return [dot, bubble, pop]


# ---------------- F06 : 겹치는 오버레이 ----------------
f06_overlay = html.Div(
    id="f06-overlay", className="box f06-layer",
    children=[
        html.Div([tag("F06"),
                  html.Span("시간별 센서 이상", className="panel-title"),
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
        html.Div([tag("F05"), html.Span("설비 종합 진단", className="panel-title")],
                 className="summary-hdr"),
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
    children=html.Div(className="box panel-collapse panel-collapse--f07",
                      children=[
        html.Div(className="panel-hdr", children=[
            tag("F07"),
            html.Span("최적 발주 시점 및 비용 분석 —", className="panel-title"),
            html.Span("--", id="f07-part-label", className="panel-title f07-part-label"),
            html.Div(className="btns", children=[
                dbc.Button("담기", id="btn-add-cart", size="sm",
                           color="primary", n_clicks=0),
                dbc.Button("닫기", id="btn-f07-close", size="sm",
                           color="light", n_clicks=0),
            ]),
        ]),
        dbc.Row(className="g-2", children=[
            dbc.Col(md=12, lg=5, children=html.Div(className="box", children=[
                html.Div("비용 최소 발주 시점", className="sub-title"),
                dcc.Graph(id="f07-cost-curve", figure={}, responsive=True,
                          config={"displayModeBar": False},
                          style={"height": "clamp(140px,20vh,190px)"}),
            ])),
            dbc.Col(md=6, lg=3, children=html.Div(className="box", children=[
                html.Div("발주 및 재고 정보", className="sub-title"),
                html.Div(id="f07-order-info",
                         children=ghost("발주마감일 / 권장수량 / 조달기간 / 대응여유", 150)),
            ])),
            dbc.Col(md=6, lg=4, children=html.Div(className="box", children=[
                html.Div("시나리오 비교", className="sub-title"),
                dbc.Row(className="g-2", children=[
                    dbc.Col(xs=12, sm=4, children=html.Div(className="box f07-scenario",
                        children=["오늘 발주", html.Div("--", id="f07-cost-d0", className="f07-scenario-value")])),
                    dbc.Col(xs=12, sm=4, children=html.Div(className="box f07-scenario",
                        children=["1주 대기", html.Div("--", id="f07-cost-d7", className="f07-scenario-value")])),
                    dbc.Col(xs=12, sm=4, children=html.Div(className="box f07-scenario",
                        children=["2주 대기", html.Div("--", id="f07-cost-d14", className="f07-scenario-value")])),
                ]),
            ])),
        ]),
    ]),
)

# ---------------- F08-a : 협력사 ----------------
f08_supplier = dbc.Collapse(
    id="f08-supplier-collapse", is_open=False,
    children=html.Div(className="box panel-collapse panel-collapse--f08",
                      children=[
        html.Div(className="panel-hdr", children=[
            tag("F08"),
            html.Span("협력사 정보", className="panel-title"),
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
    children=html.Div(className="box panel-collapse panel-collapse--f08",
                      children=[
        html.Div(className="panel-hdr", children=[
            tag("F08"),
            html.Span("교체 이력", className="panel-title"),
            html.Div(className="btns", children=[
                dbc.Button("닫기", id="btn-f08-history-close",
                           size="sm", color="light", n_clicks=0)]),
        ]),
        html.Div(id="f08-history-table", className="table-scroll",
                 children=ghost("교체일 / 부품 / 담당자 / 비용 / 비고", 130)),
    ]),
)

# ---------------- layout ----------------
def create_detail_layout(machine_id=None):
    selected = machine_id if machine_id in MACHINES else MACHINES[0]
    return html.Div(className="page-detail", children=[
        dcc.Store(id="store-selected-machine", data=selected),
        dcc.Store(id="store-selected-comp", data=None),

        html.Div(className="hdr", children=[
            html.Span("설비 상세 —", className="hdr-title"),
            html.Span(f"M-{selected:03d}", id="detail-machine-name",
                      className="hdr-title hdr-machine"),
            dcc.Dropdown(
                id="detail-machine-select",
                options=[{"label": f"M-{machine:03d}", "value": machine} for machine in MACHINES],
                value=selected, clearable=False,
                className="detail-machine-select",
            ),
            html.Span(f"기준일 {AS_OF}", id="detail-asof", className="hdr-right hdr-asof"),
        ]),
        html.P(
            "부품별 고장 예측과 센서 이상은 서로 다른 결과입니다. 센서 분석은 현재 설비의 저장된 관측과 IF 결과를 사용하며, 발주·이력은 UI 프레임입니다.",
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
            summary = ("예측 없음", "부품별 위험 점수 없음", diagnosis["text"])
        else:
            score = (f"{diagnosis['highest_score']:.1%}" if diagnosis["calibrated"]
                     else f"{diagnosis['highest_score']:.3f}")
            kind = "고장 확률" if diagnosis["calibrated"] else "미보정 위험 점수"
            summary = (f"최대 위험: {diagnosis['highest_component']}",
                       f"향후 {diagnosis['horizon_days']}일 · {kind} {score}",
                       diagnosis["text"])
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
    return html.Span(label, className="f06-summary-alert" if total else "f06-summary-ok")


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
