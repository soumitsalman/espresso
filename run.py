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
        env.load_env("./app/api/api.toml")
        from app.api import router
        router.run()
    elif mode == "mcp":
        env.load_env("./app/api/mcp.toml")
        from app.api import mcprouter
        mcprouter.run()
    elif mode == "vanilla":
        env.load_env("./app/web/vanilla.toml")
        from app.web import vanilla
        vanilla.run()  
    # else:
    #     from app.web import vanilla_router
    #     vanilla_router.run()

