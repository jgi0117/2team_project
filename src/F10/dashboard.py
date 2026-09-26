"""Compact equipment-level anomaly overview, aligned with F09's cutoff."""

import pandas as pd
from src.UI.heatmap_panel import panel_contents

from src.F09.heatmap import machine_ids
from .heatmap import build_heatmap, load_predictions


def create_layout(as_of, data=None):
    data = load_predictions() if data is None else data
    figure, meta = build_heatmap(data, as_of, machines=machine_ids())
    observed = meta["observed_at"]
    date_label = "결과 없음" if pd.isna(observed) else f"{observed:%Y-%m-%d}"
    return panel_contents(
        title="설비별 이상 위험", title_id="stats-f10-title",
        meaning="현재 센서 패턴이 평소와 다른 정도", date=date_label,
        graph_id="f10-heatmap", figure=figure, anomaly=True,
    )
