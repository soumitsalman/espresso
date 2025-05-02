from nicegui import ui
from app.web.renderer import GOOGLE_ANALYTICS_SCRIPT, PRIMARY_COLOR, SECONDARY_COLOR, CSS_FILE
from app.shared.env import *

def run():
    # app.add_middleware(SessionMiddleware, secret_key=APP_STORAGE_SECRET) # needed for oauth
    # # app.state.limiter = limiter
    # # app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    ui.add_head_html(GOOGLE_ANALYTICS_SCRIPT, shared=True)
    ui.add_css(CSS_FILE)
    ui.colors(primary=PRIMARY_COLOR, secondary=SECONDARY_COLOR)  
    ui.label("🚧 Under Maintenance! 🚧").classes("text-h5 self-center")
    ui.label("We are taking an epic 💩! But do not worry, we'll get the 🚽 back to you sparkling clean ... soooon!").classes("self-center")
    ui.run(
        title=APP_NAME, 
        storage_secret=APP_STORAGE_SECRET,
        dark=True, 
        favicon="./images/favicon.ico", 
        port=8080, 
        show=False,
        uvicorn_reload_includes="*.py,*/web/styles.css",
        proxy_headers=True
    )