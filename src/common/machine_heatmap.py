"""A numbered tile per machine, shared by the F09 and F10 overviews."""

import math

import pandas as pd
import plotly.graph_objects as go


RISK_COLORS = [[0, "#edf4fa"], [0.25, "#a9d4df"], [0.5, "#f1d18a"],
               [0.75, "#e98764"], [1, "#b82e43"]]
ANOMALY_COLORS = [[0, "#edf4fa"], [0.35, "#a9d4df"], [0.45, "#f1d18a"],
                  [0.5, "#e98764"], [0.65, "#b82e43"], [1, "#7f1833"]]


def machine_grid(machines, scores, details, *, colors=RISK_COLORS, white_from=0.85):
    """Keep fixed machine positions; absent scores are gray, never zero."""
    columns = min(20, max(1, len(machines)))
    rows = max(1, math.ceil(len(machines) / columns))
    z = [[None] * columns for _ in range(rows)]
    background = [[None] * columns for _ in range(rows)]
    hover = [[""] * columns for _ in range(rows)]
    x, y, labels, text_colors = [], [], [], []
    for index, machine in enumerate(machines):
        row, column = divmod(index, columns)
        value = scores.get(machine)
        known = value is not None and pd.notna(value)
        z[row][column] = float(value) if known else None
        background[row][column] = 0
        hover[row][column] = f"<b>M-{machine:03d}</b><br>" + details.get(machine, "결과 없음")
        x.append(column)
        y.append(row)
        labels.append(f"{machine:03d}")
        text_colors.append("#fff" if known and value >= white_from else "#253e55")
    figure = go.Figure()
    figure.add_trace(go.Heatmap(z=background, x=list(range(columns)), y=list(range(rows)),
                               colorscale=[[0, "#e4e8ed"], [1, "#e4e8ed"]], showscale=False,
                               customdata=hover, hovertemplate="%{customdata}<extra></extra>",
                               xgap=5, ygap=5, hoverongaps=False))
    figure.add_trace(go.Heatmap(z=z, x=list(range(columns)), y=list(range(rows)),
                               coloraxis="coloraxis", customdata=hover,
                               hovertemplate="%{customdata}<extra></extra>",
                               xgap=5, ygap=5, hoverongaps=False))
    figure.add_trace(go.Scatter(x=x, y=y, mode="text", text=labels,
                               textfont=dict(size=12, color=text_colors),
                               hoverinfo="skip", showlegend=False))
    figure.update_layout(
        template="plotly_white", autosize=True, margin=dict(l=0, r=0, t=0, b=0),
        xaxis=dict(visible=False, fixedrange=True, range=[-0.5, columns - 0.5]),
        yaxis=dict(visible=False, fixedrange=True, range=[rows - 0.5, -0.5]),
        coloraxis=dict(cmin=0, cmax=1, showscale=False, colorscale=colors),
        font=dict(family="Malgun Gothic, sans-serif"), plot_bgcolor="white",
        hoverlabel=dict(bgcolor="white"), dragmode=False,
    )
    return figure
