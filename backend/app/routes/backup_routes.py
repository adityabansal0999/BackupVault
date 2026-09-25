from fastapi import APIRouter, HTTPException
from backend.app.services import backup_service
from backend.app.repositories import backup_repo
from backend.app.models.schemas import BackupCreateRequest

router = APIRouter(prefix="/api", tags=["backups"])

@router.post("/backups")
def create_backup(req: BackupCreateRequest):
    result = backup_service.create_backup(req.database_name, req.created_by)
    if result["status"] == "FAILED":
        raise HTTPException(500, result.get("error"))
    return result

@router.get("/backups")
def list_backups(limit: int = 20, offset: int = 0, date_from: str = None, date_to: str = None):
    return backup_repo.list_backups(limit, offset, date_from, date_to)

@router.get("/status")
def status():
    return backup_repo.get_status_summary()
