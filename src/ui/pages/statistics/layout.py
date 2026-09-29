"""Two equipment overviews: sensor anomalies above failure risk."""

from dash import html

from src.F09.dashboard import create_layout
from src.F09.heatmap import load_predictions
from src.F10.dashboard import create_layout as create_anomaly_layout
from src.ui.config import upto_as_of


def create_statistics_layout(predictions=None, as_of=None, horizon=None):
    predictions = upto_as_of(load_predictions() if predictions is None else predictions, as_of)
    return html.Main(
        [
            html.Header([
                html.H1("통계"),
                html.P(["설비 100대를 한 화면에서 비교해 먼저 확인할 설비를 찾는 화면입니다. ",
                        html.B("위"), "는 지금 센서가 평소와 얼마나 다른지(1시간 단위), ",
                        html.B("아래"), "는 앞으로 며칠 안에 고장 날 위험이 얼마나 높은지(일 단위)를 보여줍니다. "
                        "붉은 칸일수록 먼저 확인하고, 칸을 누르면 그 설비 화면으로 이동합니다."],
                       className="st-intro-text"),
            ], className="st-intro"),
            html.Section(
                create_anomaly_layout(as_of or predictions.as_of.max()),
                id="stats-f10-content", className="risk-panel",
                **{"aria-labelledby": "stats-f10-title"},
            ),
            html.Section(
                create_layout(predictions, predictions.as_of.max(), horizon),
                id="stats-f09-content",
                className="risk-panel",
                **{"aria-labelledby": "stats-f09-title"},
            ),
        ],
        className="ui-statistics",
        id="statistics-page",
    )
