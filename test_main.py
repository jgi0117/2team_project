import dash

from src.ui.pages.main import layout

app = dash.Dash(
    __name__,
    assets_folder="src/ui/assets",
    suppress_callback_exceptions=True,
)

app.layout = layout

if __name__ == "__main__":
    app.run(debug=True, port=8050)
