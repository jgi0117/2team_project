"""A compact, control-free overview of all machines."""

from src.UI.heatmap_panel import panel_contents

from .heatmap import build_heatmap, load_predictions, machine_ids


def create_layout(data=None):
    data = load_predictions() if data is None else data
    as_of = data.as_of.max()
    latest = data.loc[data.as_of.eq(as_of)]
    version = sorted(latest.model_version.unique())[-1]
    horizons = sorted(latest.loc[latest.model_version.eq(version)].horizon_days.unique())
    horizon = 28 if 28 in horizons else int(horizons[-1])
    figure, _ = build_heatmap(data, as_of, horizon, version, machines=machine_ids())
    return panel_contents(
        title="설비별 고장 위험", title_id="stats-f09-title",
        meaning=f"향후 {horizon}일 내 고장 가능성", date=as_of,
        graph_id="f09-heatmap", figure=figure,
    )
