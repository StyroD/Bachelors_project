from shiny import App
from ui import app_ui
from server import server

app = App(app_ui, server)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
