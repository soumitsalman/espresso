from app.shared.env import load_env, MODE
load_env()

if __name__ in {"__main__", "__mp_main__"}:

    if MODE == "MAINTENANCE":
        from app.web import maintenance
        maintenance.run()
    else:
        from app.web import router
        router.run()
