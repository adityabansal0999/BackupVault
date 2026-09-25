from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class BackupCreateRequest(BaseModel):
    database_name: str = "customer_db"
    created_by: str = "manual"

class BackupResponse(BaseModel):
    backup_id: int
    file_name: str
    file_path: str
    file_size_bytes: int
    status: str
    created_at: datetime

class RestoreRequest(BaseModel):
    file_name: str
    target_database: str
    confirm: bool = False

class VerifyResponse(BaseModel):
    backup_id: int
    result: str
    file_exists: bool
    file_size_ok: bool
    gzip_valid: bool
