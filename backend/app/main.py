import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from backend.app.routes.backup_routes import router
from backend.app.scheduler import start_scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.scheduler = None
    try:
        app.state.scheduler = start_scheduler()
    except Exception:
        logging.getLogger("backupvault").exception("Scheduler NOT started")
    yield
    if app.state.scheduler:
        app.state.scheduler.shutdown(wait=False)

app = FastAPI(title="BackupVault API", version="1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(router)

base = Path(__file__).resolve().parents[2]
dash = base / "dashboard"
if dash.exists():
    app.mount("/dashboard", StaticFiles(directory=str(dash), html=True), name="dashboard")
else:
    try:
        app.mount("/dashboard", StaticFiles(directory="dashboard", html=True), name="dashboard")
    except:
        pass

from fastapi.responses import RedirectResponse

@app.get("/")
def root():
    return RedirectResponse(url="/dashboard")
