from nicegui import ui
from app.shared.env import *
from app.web.renderer import GOOGLE_ANALYTICS_SCRIPT, PRIMARY_COLOR, SECONDARY_COLOR, CSS_FILE


def run():
    ui.add_head_html(GOOGLE_ANALYTICS_SCRIPT.format(config.app.google_analytics_id), shared=True)
    ui.add_css(CSS_FILE)
    ui.colors(primary=PRIMARY_COLOR, secondary=SECONDARY_COLOR)  
    ui.label("🚧 Under Maintenance! 🚧").classes("text-h5 self-center")
    ui.label("We are taking an epic 💩! But do not worry, we'll get the 🚽 back to you sparkling clean ... soooon!").classes("self-center")
    ui.run(
        title=config.app.name, 
        dark=True, 
        favicon="./images/favicon.ico", 
        port=8080, 
        show=False,
    )