import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import typer
from rich import print as rprint

app = typer.Typer(help="BackupVault CLI")

@app.command()
def backup(database: str = typer.Option(None)):
    from backend.app.services.backup_service import create_backup
    rprint(create_backup(database, created_by="cli"))

@app.command()
def verify(backup_id: int):
    from backend.app.services.verification_service import verify_backup
    rprint(verify_backup(backup_id))

@app.command()
def history(limit: int = typer.Option(20, "--limit"), date_from: str = typer.Option(None, "--date-from"), date_to: str = typer.Option(None, "--date-to")):
    from backend.app.repositories.backup_repo import get_history
    data = get_history(limit, 0, date_from, date_to)
    rprint(f"Total: {data['total']} backups | Storage: {data['total_storage']} bytes")
    for r in data["items"]:
        rprint(f"{r['backup_id']} | {r['file_name']} | {r['file_size_bytes']} | {r['status']} | {r['verification_status']} | {r['created_at']} | {r['created_by']} | {r['file_path']}")

@app.command()
def list(limit: int = typer.Option(20, "--limit")):
    from backend.app.repositories.backup_repo import list_backups
    rows = list_backups(limit)
    for r in rows:
        rprint(f"{r['file_name']} | {r['file_size_bytes']} | {r['status']} | {r['created_at']} | {r['database_name']} | {r['created_by']}")

@app.command()
def restore(date: str = typer.Option(..., "--date"), target: str = typer.Option("customer_db")):
    from backend.app.repositories.backup_repo import list_backups
    rows = list_backups(100)
    matched = [r for r in rows if date in r["file_name"]]
    if not matched:
        rprint(f"No backup for {date}")
        raise typer.Exit(1)
    file_name = matched[0]["file_name"]
    if not typer.confirm(f"OVERWRITE {target} with {file_name}? Can't undo! Continue?"):
        raise typer.Abort()
    from backend.app.services.restore_service import restore_backup
    rprint(restore_backup(file_name, target, confirm=True))

@app.command()
def test(backup: str = typer.Option(..., "--backup")):
    from backend.app.db import get_conn, load_sql
    conn = get_conn()
    cur = conn.cursor(dictionary=True)
    cur.execute(load_sql("get_backup_id_by_filename"), (backup,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        rprint("Not found")
        raise typer.Exit(1)
    from backend.app.services.restore_service import test_restore_auto
    rprint(test_restore_auto(row["backup_id"]))

@app.command()
def schedule():
    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    from backend.app.scheduler import run_blocking
    run_blocking()

@app.command()
def status():
    from backend.app.repositories.backup_repo import get_status_summary
    rprint(get_status_summary())

if __name__ == "__main__":
    app()
