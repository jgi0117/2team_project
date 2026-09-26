import dash
import dash_bootstrap_components as dbc
from src.ui.pages.detail import layout as detail_layout

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True,
    meta_tags=[{"name": "viewport",
                "content": "width=device-width, initial-scale=1"}],
)
app.title = "설비보전 관리 대시보드"
app.layout = detail_layout

if __name__ == "__main__":
    app.run(debug=True, port=8050)
