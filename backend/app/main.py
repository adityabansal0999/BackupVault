import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.routes.backup_routes import router
from backend.app.scheduler import start_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
app = FastAPI(title="BackupVault API", version="1.0")
app.state.scheduler = None

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(router)


@app.on_event("startup")
def on_startup():
    try:
        app.state.scheduler = start_scheduler()
    except Exception:
        logging.getLogger("backupvault").exception("Scheduler NOT started")


@app.on_event("shutdown")
def on_shutdown():
    if app.state.scheduler:
        app.state.scheduler.shutdown(wait=False)


@app.get("/")
def root():
    return {"message": "BackupVault API running", "docs": "/docs"}
