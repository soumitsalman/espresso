import os
from dotenv import load_dotenv
from app.shared.utils import initialize_app

load_dotenv()
mode = os.getenv("MODE")

if __name__ in {"__main__", "__mp_main__"}:

    if mode == "maintenance":
        from app.web import maintenance
        maintenance.run()
    elif mode == "api":
        initialize_app("./factory/api.toml")
        from app.api import apirouter
        apirouter.run()
    elif mode == "mcp":
        initialize_app("./factory/mcp.toml")
        from app.api import mcprouter
        mcprouter.run()
    elif mode == "web":
        initialize_app("./factory/web.toml")
        from app.web import router
        apirouter.run()  
    else:
        raise ValueError(f"Unknown MODE: {mode}")

