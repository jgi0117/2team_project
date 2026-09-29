"""Selectable-horizon overview of all machines."""

import pandas as pd
from dash import Input, Output, State, callback, dcc

from src.ui.pages.statistics.heatmap_panel import panel_contents
from src.ui.config import UI_AS_OF

from .heatmap import build_heatmap, load_predictions, machine_ids

SELECTABLE_HORIZONS = (7, 14, 42)


def _view(data, as_of, horizon_days=None):
    as_of = pd.Timestamp(as_of).strftime("%Y-%m-%d")
    latest = data.loc[data.as_of.eq(as_of)]
    if latest.empty:
        raise ValueError("No failure predictions at the statistics cutoff")
    version = sorted(latest.model_version.unique())[-1]
    available = {int(value) for value in
                 latest.loc[latest.model_version.eq(version)].horizon_days.unique()}
    horizons = [days for days in SELECTABLE_HORIZONS if days in available]
    if not horizons:
        raise ValueError("No selectable prediction horizons at the statistics cutoff")
    default = 7 if 7 in horizons else horizons[0]
    horizon = default if horizon_days is None else int(horizon_days)
    if horizon not in horizons:
        horizon = default
    figure, meta = build_heatmap(data, as_of, horizon, version, machines=machine_ids())
    score_name = "고장 확률" if meta["calibrated"] else "상대 위험 점수"
    purpose = ("즉시 대응용" if horizon == 7 else
               "단기 정비계획 참고용" if horizon == 14 else
               "장기 조달계획 참고용")
    title = f"향후 {horizon}일 설비 위험 분포"
    meaning = f"일 단위 · 기준일부터 {horizon}일 안 {score_name} · {purpose} · 부품 4개 중 가장 높은 점수"
    return figure, title, meaning, horizons, horizon


def create_layout(data=None, as_of=None, horizon_days=None):
    data = load_predictions() if data is None else data
    as_of = data.as_of.max() if as_of is None else pd.Timestamp(as_of).strftime("%Y-%m-%d")
    figure, title, meaning, horizons, horizon = _view(data, as_of, horizon_days)
    controls = dcc.RadioItems(
        id="f09-horizon",
        options=[{"label": f"{days}일", "value": days} for days in horizons],
        value=horizon,
        inline=True,
        className="risk-horizon-control",
        inputClassName="risk-horizon-input",
        labelClassName="risk-horizon-button",
    )
    return panel_contents(
        title=title, title_id="stats-f09-title", meaning=meaning,
        meaning_id="stats-f09-meaning", controls=controls, date=f"{as_of} 예측",
        graph_id="f09-heatmap", figure=figure,
    )


@callback(
    Output("f09-heatmap", "figure"),
    Output("stats-f09-title", "children"),
    Output("stats-f09-meaning", "children"),
    Input("f09-horizon", "value"),
    State("store-as-of", "data"),
)
def update_horizon(horizon_days, as_of=None):
    data = load_predictions()
    cutoff = data.loc[data.as_of.le(as_of or UI_AS_OF)].as_of.max()   # 선택 기준일 직전 예측일
    figure, title, meaning, _, _ = _view(data, cutoff, horizon_days)
    return figure, title, f"{meaning} · 설비 칸 클릭 시 상세 보기"
