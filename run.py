import os
from dotenv import load_dotenv
from app.shared import env

load_dotenv()
mode = os.getenv("MODE")

if __name__ in {"__main__", "__mp_main__"}:

    if mode == "maintenance":
        from app.web import maintenance
        maintenance.run()
    elif mode == "api":
        from app.api import router
        vanilla.run()
    elif mode == "vanilla":
        env.load_env("./env.toml", "./app/web/vanilla.toml")
        from app.web import vanilla
        vanilla.run()  
    # else:
    #     from app.web import vanilla_router
    #     vanilla_router.run()

