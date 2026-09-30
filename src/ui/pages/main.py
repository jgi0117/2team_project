from dash import html, dcc, Input, Output, State, ALL, callback, ctx


# UI Frame 확인용 임시 데이터
# 실제 데이터 연결 시 이 부분을 예측/재고/발주 데이터로 교체
TOP5_DATA = {
    "2024-10-07": [
        ("M-071", 56, "재고 위험"),
        ("M-023", 52, "발주 긴급"),
        ("M-102", 48, "예상 손실"),
        ("M-055", 44, "대응 여유"),
        ("M-087", 36, "설비 위험도"),
    ],
    "2024-10-18": [
        ("M-023", 85, "설비 위험도"),
        ("M-071", 56, "발주 긴급"),
        ("M-102", 48, "예상 손실"),
        ("M-055", 44, "재고 위험"),
        ("M-087", 36, "대응 여유"),
    ],
    "2024-10-28": [
        ("M-023", 91, "설비 위험도"),
        ("M-071", 82, "재고 위험"),
        ("M-055", 67, "발주 긴급"),
        ("M-102", 48, "예상 손실"),
        ("M-087", 36, "대응 여유"),
    ],
}

DEFAULT_TOP5 = TOP5_DATA["2024-10-18"]


def make_calendar():
    events = {
        7: "발주 마감",
        10: "정비 예정",
        15: "교체 임박",
        18: "발주 마감",
        21: "발주 마감",
        28: "기한 초과",
    }

    cells = []

    for day in range(1, 32):
        if day in events:
            cells.append(
                html.Button(
                    [
                        html.Span(str(day)),
                        html.Small(events[day]),
                    ],
                    id={"type": "mn-date", "date": f"2024-10-{day:02d}"},
                    className="mn-calendar-cell",
                )
            )
        else:
            cells.append(
                html.Button(
                    str(day),
                    id={"type": "mn-date", "date": f"2024-10-{day:02d}"},
                    className="mn-calendar-cell",
                )
            )

    return html.Div(
        [
            html.Div(
                ["일", "월", "화", "수", "목", "금", "토"],
                className="mn-week",
            ),
            html.Div(cells, className="mn-calendar"),
            html.Button(
                "우선 확인 설비 TOP5 보기",
                id="mn-show-top5",
                className="mn-action-btn",
            ),
        ]
    )


def make_top5(data, selected_date):
    return html.Div(
        [
            html.Div(
                [
                    html.Strong("우선 확인 설비 TOP5"),
                    html.Span(f"{selected_date} 기준"),
                ],
                className="mn-top5-header",
            ),
            dcc.Dropdown(
                id="mn-top5-sort",
                options=[
                    {"label": "설비 위험도", "value": "설비 위험도"},
                    {"label": "재고 위험", "value": "재고 위험"},
                    {"label": "발주 긴급", "value": "발주 긴급"},
                    {"label": "예상 손실", "value": "예상 손실"},
                    {"label": "대응 여유", "value": "대응 여유"},
                ],
                value="설비 위험도",
                clearable=False,
                placeholder="정렬 기준 선택",
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Span(str(i), className="mn-rank"),
                            html.Strong(machine),
                            html.Span(f"{risk}%"),
                        ],
                        className="mn-top5-row",
                    )
                    for i, (machine, risk, reason) in enumerate(data, 1)
                ],
                id="mn-top5-list",
            ),
            html.Small(
                "정렬 기준: 설비 위험도 · 재고 위험 · 발주 긴급 · 예상 손실 · 대응 여유",
                className="mn-guide",
            ),
        ],
        className="box mn-f02",
    )

def make_summary_cards():
    cards = [
        ("경고 설비", "8대", "△2대", "mn-summary-red"),
        ("교체기한 임박", "1대", "△1대", "mn-summary-blue"),
        ("기한 초과", "1대", "△0대", "mn-summary-red"),
        ("이번 주 발주 필요", "3건", "", ""),
        ("미조치 시 예상 손실", "2,400 만원", "", "mn-summary-red"),
        ("지금 조치 시 절감 효과", "1,850 만원", "", "mn-summary-green"),
    ]

    return html.Div(
        [
            html.Div(
                [
                    html.Div(title, className="mn-summary-title"),
                    html.Div(
                        [
                            html.Strong(value),
                            html.Span(change),
                        ],
                        className="mn-summary-value",
                    ),
                ],
                className=f"mn-summary-card {extra}".strip(),
            )
            for title, value, change, extra in cards
        ],
        className="mn-summary-cards",
    )


layout = html.Div(
    [
        # ① F03 — TOP5가 열리고 닫혀도 유지
        html.Div(
            [
                html.Strong("F03  AI 한 줄 대응 요약"),
                html.Span(
                    "이번 주 발주 필요 3건 · 미조치 시 예상손실 2,400만원 · 지금 조치 시 1,850만원 절감",
                    id="mn-summary",
                ),
            ],
            className="mn-f03",
            id="mn-f03",
        ),

        # 가운데 영역: TOP5는 닫혀 있을 때 화면에 보이지 않음
        html.Div(
            [
                html.Div(
                    [
                        html.Strong("현재 상황"),
                        make_summary_cards(),
                    ],
                    className="box mn-current-summary",
                ),

                html.Div(
                    [
                        html.Strong("F04  To-Do"),
                        html.P("날짜를 선택한 뒤 우선 확인 설비를 조회"),
                        make_calendar(),
                    ],
                    className="box mn-todo",
                ),

                # TOP5 영역은 wrapper가 항상 존재하지만 닫힌 상태에서는 display:none
                html.Div(
                    [
                        html.Div(id="mn-top5-panel"),
                        html.Button(
                            "TOP5 닫기",
                            id="mn-close-top5",
                            className="mn-action-btn mn-close-btn",
                        ),
                    ],
                    id="mn-f02-slot",
                    className="mn-f02-slot mn-f02-slot-closed",
                ),
            ],
            id="mn-middle",
            className="mn-middle-grid mn-middle-closed",
        ),

        # ⑤ + ⑥ 현재 상황/To-Do 아래 전체 폭
        html.Div(
            [
                html.Div(
                    [
                        html.Strong("F01  확률 급상승 알림"),
                        html.Div(
                            "전일 대비 고장 확률이 크게 상승한 설비 TOP3",
                            className="mn-placeholder",
                        ),
                    ],
                    className="box mn-bottom-box",
                ),
                html.Div(
                    [
                        html.Strong("F02  재고 × 위험 교차"),
                        html.Div(
                            "부품별 재고량과 위험 설비를 비교하는 영역",
                            className="mn-placeholder",
                        ),
                    ],
                    className="box mn-bottom-box",
                ),
            ],
            className="mn-bottom-grid",
        ),

        # ⑦ F04 — TOP5 열림/닫힘과 관계없이 섹션 자체는 유지
        html.Div(
            [
                html.Strong("F04  위험 대응률"),
                html.Div(
                    "예측 위험 설비 / 실제 고장 / 대응 성과 추이를 표시하는 영역",
                    className="mn-placeholder",
                ),
            ],
            className="box mn-history",
            id="mn-history",
        ),

    ],
    className="mn-page",
)


@callback(
    Output("mn-top5-panel", "children"),
    Output("mn-f02-slot", "className"),
    Output("mn-middle", "className"),
    Input("mn-show-top5", "n_clicks"),
    Input("mn-close-top5", "n_clicks"),
    State({"type": "mn-date", "date": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def toggle_top5(show_click, close_click, date_clicks):
    triggered = ctx.triggered_id

    # 닫기 버튼은 layout에 항상 존재하고, 닫힌 상태에서는 CSS로만 숨겨짐.
    if triggered == "mn-close-top5":
        return [], "mn-f02-slot mn-f02-slot-closed", "mn-middle-grid mn-middle-closed"

    selected_date = "2024-10-18"
    if date_clicks:
        counts = [value or 0 for value in date_clicks]
        if max(counts) > 0:
            selected_day = counts.index(max(counts)) + 1
            selected_date = f"2024-10-{selected_day:02d}"

    data = TOP5_DATA.get(selected_date, DEFAULT_TOP5)
    top5 = make_top5(data, selected_date)

    # TOP5가 열리면 가운데 3칸, 닫히면 2칸으로 돌아감.
    # F03과 하단 F04는 그대로 유지됨.
    return top5, "mn-f02-slot mn-f02-slot-open", "mn-middle-grid mn-middle-open"
