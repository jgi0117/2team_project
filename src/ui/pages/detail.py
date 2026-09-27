# src/ui/pages/detail.py
# 설비 상세 페이지 - 프레임(빈 박스 + id + 펼침/접힘) / 반응형
from dash import html, dcc, Input, Output, callback, ctx
import dash_bootstrap_components as dbc

COMPS    = ["comp1", "comp2", "comp3", "comp4"]
DECISION = {"comp1": 8, "comp2": 42, "comp3": 16, "comp4": 24}
ADOPTED  = {"comp1": True, "comp2": False, "comp3": True, "comp4": True}
HORIZONS = [7, 8, 14, 16, 21, 24, 28, 35, 42]

# 설비 이미지 위 부품 좌표(%) — 이미지 바뀌면 이 숫자만 수정
POS = {
    "comp1": {"top": "16%", "left": "22%"},
    "comp2": {"top": "26%", "left": "62%"},
    "comp3": {"top": "58%", "left": "32%"},
    "comp4": {"top": "68%", "left": "72%"},
}


def tag(code, color="#1f4e9c"):
    return html.Span(code, className="ftag", style={"background": color})


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
            html.Div("--%", id=f"hs-prob-{comp}",
                     className="hotspot-prob", style={"color": color}),
            html.Div("" if on else "미채택(안전재고)", className="hs-note",
                     style={"fontSize": "10px", "color": "#9aa5b1"}),
        ],
    )

    pop = dbc.Popover(
        [dbc.PopoverHeader(f"{comp} 기간별 고장 확률"),
         dbc.PopoverBody(
             html.Div(className="pop-scroll", children=html.Div(
                 id=f"hs-pop-table-{comp}",
                 children=html.Table([
                     html.Thead(html.Tr([html.Th("기간")] +
                                        [html.Th(f"{h}일") for h in HORIZONS])),
                     html.Tbody(html.Tr([html.Td("확률")] +
                                        [html.Td("--") for _ in HORIZONS])),
                 ], style={"fontSize": "11px"}))))],
        id=f"hs-pop-{comp}", target=f"hotspot-{comp}",
        trigger="hover", placement="auto",
    )
    return [dot, bubble, pop]


# ---------------- F06 : 겹치는 오버레이 ----------------
f06_overlay = html.Div(
    id="f06-overlay", className="box f06-layer",
    children=[
        html.Div([tag("F06", "#7b1fa2"),
                  html.Span("센서 이상 및 위험 근거 분석", style={"fontWeight": 700})],
                 className="panel-hdr"),
        dcc.Graph(id="f06-sensor-graph", figure={}, responsive=True,
                  config={"displayModeBar": False},
                  style={"height": "clamp(90px,13vh,130px)"}),
        html.Div(className="f06-row", children=[
            html.Div(id="f06-risk-gauge", children=ghost("위험률", 84), className="f06-gauge"),
            html.Div(html.Div(id="f06-reason-table",
                              children=ghost("근거 1~3위", 84)),
                     className="f06-reason"),
        ]),
        html.Div("이상추이 이유 진단 : --", id="f06-diagnosis",
                 style={"marginTop": "8px", "fontSize": "12px",
                        "fontWeight": 700, "color": "#c62828"}),
    ],
)

# ---------------- F05 : 좌상단 종합 진단 ----------------
f05_summary = html.Div(
    id="f05-summary", className="box summary-card",
    children=[
        html.Div([tag("F05"), html.Span("설비 종합 진단",
                                        style={"fontWeight": 700, "fontSize": "13px"})],
                 style={"display": "flex", "gap": "6px", "alignItems": "center"}),
        html.Div("--", id="f05-summary-days", className="summary-days"),
        html.Div("예측 고장 시기", id="f05-summary-note", className="summary-sub"),
        html.Div("근거: --", id="f05-summary-basis", className="summary-sub"),
    ],
)

# ---------------- F05 무대 ----------------
f05_stage = html.Div(className="stage", children=[
    html.Div(className="stage-canvas", children=[
        html.Div(id="f05-equip-img", className="stage-bg",
                 children=html.Div("설비 이미지 / 3D 영역")),
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
            tag("F07", "#ef6c00"),
            html.Span("최적 발주 시점 및 비용 분석 —", style={"fontWeight": 700}),
            html.Span("--", id="f07-part-label",
                      style={"fontWeight": 700, "color": "#ef6c00"}),
            html.Div(className="btns", children=[
                dbc.Button("담기", id="btn-add-cart", size="sm",
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
            tag("F08", "#2e7d32"),
            html.Span("협력사 정보", style={"fontWeight": 700}),
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
            tag("F08", "#2e7d32"),
            html.Span("교체 이력", style={"fontWeight": 700}),
            html.Div(className="btns", children=[
                dbc.Button("닫기", id="btn-f08-history-close",
                           size="sm", color="light", n_clicks=0)]),
        ]),
        html.Div(id="f08-history-table", style={"overflowX": "auto"},
                 children=ghost("교체일 / 부품 / 담당자 / 비용 / 비고", 130)),
    ]),
)

# ---------------- layout ----------------
layout = html.Div(className="page-detail", children=[
    dcc.Store(id="store-selected-machine", data=None),
    dcc.Store(id="store-selected-comp", data=None),

    html.Div(className="hdr", children=[
        html.Span("설비 상세 —", style={"fontSize": "clamp(15px,1.6vw,18px)",
                                       "fontWeight": 700}),
        html.Span("--", id="detail-machine-name",
                  style={"fontSize": "clamp(15px,1.6vw,18px)", "fontWeight": 800}),
        html.Span("기준일 --", id="detail-asof", className="hdr-right",
                  style={"fontSize": "12px", "color": "#667"}),
    ]),

    f05_stage,
    f07_panel,
    f08_supplier,
    f08_history,
])


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
