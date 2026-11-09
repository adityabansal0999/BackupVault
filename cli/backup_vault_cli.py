
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import typer
from rich import print as rprint

app = typer.Typer(help="BackupVault CLI")


@app.command()
def backup(
    database: str = typer.Option(None, "--database")
):
    """Create a database backup."""
    from backend.app.services.backup_service import create_backup

    result = create_backup(database, created_by="cli")
    rprint(result)


@app.command()
def verify(backup_id: int):
    """Verify a stored backup."""
    from backend.app.services.verification_service import verify_backup

    rprint(verify_backup(backup_id))


@app.command()
def history(
    limit: int = typer.Option(20, "--limit"),
    date_from: str = typer.Option(None, "--date-from"),
    date_to: str = typer.Option(None, "--date-to"),
):
    """Display backup history."""
    from backend.app.repositories.backup_repo import get_history

    data = get_history(limit, 0, date_from, date_to)

    rprint(
        f"Total: {data['total']} backups | "
        f"Storage: {data['total_storage']} bytes"
    )

    for row in data["items"]:
        rprint(
            f"{row['backup_id']} | "
            f"{row['file_name']} | "
            f"{row['file_size_bytes']} | "
            f"{row['status']} | "
            f"{row['verification_status']} | "
            f"{row['created_at']} | "
            f"{row['created_by']} | "
            f"{row['file_path']}"
        )


@app.command("list")
def list_backups(
    limit: int = typer.Option(20, "--limit")
):
    """List available backups."""
    from backend.app.repositories.backup_repo import list_backups

    rows = list_backups(limit)

    for row in rows:
        rprint(
            f"{row['file_name']} | "
            f"{row['file_size_bytes']} | "
            f"{row['status']} | "
            f"{row['created_at']} | "
            f"{row['database_name']} | "
            f"{row['created_by']}"
        )


@app.command()
def restore(
    date: str = typer.Option(..., "--date"),
    target: str = typer.Option(
        "customer_db_restore_test",
        "--target",
    ),
):
    """Restore a verified backup into an existing empty database."""
    from backend.app.repositories.backup_repo import list_backups
    from backend.app.services.restore_service import restore_backup

    rows = list_backups(100)

    matched = [
        row for row in rows
        if date in row["file_name"]
    ]

    if not matched:
        rprint(f"[red]No backup found for: {date}[/red]")
        raise typer.Exit(code=1)

    selected = matched[0]
    file_name = selected["file_name"]

    rprint("\n[bold]Restore details[/bold]")
    rprint(f"Backup: [cyan]{file_name}[/cyan]")
    rprint(f"Target database: [cyan]{target}[/cyan]")
    rprint("The target must already exist and be empty.")
    rprint("The source and metadata databases are protected.")

    if not typer.confirm(
        "Proceed with restoration?",
        default=False,
    ):
        rprint("[yellow]Restoration cancelled.[/yellow]")
        raise typer.Abort()

    try:
        result = restore_backup(
            file_name,
            target,
            confirm=True,
            restored_by="cli",
        )

    except Exception as exc:
        rprint(f"[red]Restore could not start: {exc}[/red]")
        raise typer.Exit(code=1)

    if result["status"] == "SUCCESS":
        rprint("[green]Restore completed successfully.[/green]")
        rprint(result)
    else:
        rprint("[red]Restore failed.[/red]")
        rprint(result)
        raise typer.Exit(code=1)


@app.command()
def test(
    backup: str = typer.Option(..., "--backup")
):
    """Automatically test whether a backup can be restored."""
    from backend.app.repositories.backup_repo import (
        get_backup_by_filename,
    )
    from backend.app.services.restore_service import (
        test_restore_auto,
    )

    # Find the selected backup.
    row = get_backup_by_filename(backup)

    if not row:
        rprint(f"[red]Backup not found: {backup}[/red]")
        raise typer.Exit(code=1)

    rprint("\n[bold]Automated Restore Test[/bold]")
    rprint(f"Backup ID: {row['backup_id']}")
    rprint(f"Backup file: {backup}")
    rprint(
        "A temporary database will be created, "
        "tested and cleaned up."
    )

    try:
        result = test_restore_auto(row["backup_id"])

    except Exception as exc:
        rprint(
            f"[red]Restore test could not complete: {exc}[/red]"
        )
        raise typer.Exit(code=1)

    if result["status"] == "PASS":
        rprint(
            "[green]Automated restore test PASSED![/green]"
        )
    else:
        rprint(
            "[red]Automated restore test FAILED![/red]"
        )

    rprint(result)

    if result["status"] != "PASS":
        raise typer.Exit(code=1)


@app.command()
def schedule():
    """Run the scheduler from the CLI."""
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    from backend.app.scheduler import run_blocking

    run_blocking()


@app.command()
def status():
    """Display BackupVault status."""
    from backend.app.repositories.backup_repo import get_status_summary

    rprint(get_status_summary())


if __name__ == "__main__":
    app()
