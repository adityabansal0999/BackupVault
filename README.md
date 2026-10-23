# BackupVault

Automated backup, verification, and monitoring tool for MySQL.

Built by a team of 3 members.

---

## Status (Weeks 1-6)

| Feature | Status |
|---|---|
| Scheduled Backups | Working |
| Backup Verification (SHA-256 / Gzip) | Working |
| History and Listing | Working |
| Status Dashboard | Working |
| CLI Utility | Working |
| Point-in-Time Restore | In Progress (Weeks 7-8) |
| Automated Restore Testing | In Progress (Weeks 9-10) |
| Alert System | In Progress (Weeks 9-10) |

---

## Quickstart

`ash
# 1. Install dependencies
git clone https://github.com/adityabansal0999/BackupVault.git
cd BackupVault
pip install -r requirements.txt
cp .env.example .env

# 2. Setup database
mysql -u root -p < sql/schema_metadata.sql
mysql -u root -p < sql/schema_customer_db.sql
mysql -u root -p < sql/seed_customer_db.sql

# 3. Start server
uvicorn backend.app.main:app --reload
`
Dashboard: http://localhost:8000

---

## CLI Reference

| Command | Usage | Description |
|---|---|---|
| backup | python cli/backup_vault_cli.py backup | Run backup |
| verify | python cli/backup_vault_cli.py verify <id> | Verify backup integrity |
| list | python cli/backup_vault_cli.py list | List recent backups |
| history | python cli/backup_vault_cli.py history | Show backup history and storage |
| status | python cli/backup_vault_cli.py status | View system health summary |
| schedule | python cli/backup_vault_cli.py schedule | Start background scheduler |
