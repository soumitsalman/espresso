from app.shared.env import load_env
load_env()

if __name__ in {"__main__", "__mp_main__"}:
    from app.web import router

    router.run()
