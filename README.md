# BackupVault

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![MySQL](https://img.shields.io/badge/MySQL-8.0%2B-4479A1?logo=mysql&logoColor=white)](https://www.mysql.com/)
[![Status](https://img.shields.io/badge/Status-Milestone%20Week%206%20Complete-success)]()

> Automated, verified database snapshots with real-time health monitoring and instant disaster-recovery readiness.

---

## ⚡ Overview & Architecture

BackupVault creates safe, non-locking snapshots of live MySQL databases (--single-transaction), streams them directly into compressed archives (.sql.gz), verifies file integrity (SHA-256 + gzip validation), and catalogs all metadata in an audit database.

`	ext
  [ APScheduler / CLI / Web UI ]
                │
                ▼
      [ FastAPI Engine ]
        │            │
        ▼            ▼
 [ mysqldump ]  [ Metadata DB (MySQL) ]
        │        ├── schedule_config
        ▼        ├── backups
  [ gzip Stream ]├── backup_verifications
        │        ├── restore_tests (W9-10)
        ▼        └── alert_log
[ Disk Storage ]
`

---

## 📊 Feature Status (Weeks 1–6 Milestone)

| Feature | Description | Status |
|---|---|:---:|
| **1. Scheduled Backups** | Automated daily dump at 2 AM with streaming gzip & SHA-256 | ✅ Working |
| **2. Backup Verification** | 4-step check (file exists, size > 1KB, gzip valid, hash match) | ✅ Working |
| **3. History & Listing** | Metadata search, date-range filtering, and storage aggregation | ✅ Working |
| **4. Point-in-Time Restore**| Safe restoration to target DB with confirmation prompt | ⏳ Weeks 7–8 |
| **5. Auto Restore Testing** | Automatic post-backup test restore to disposable database | ⏳ Weeks 9–10 |
| **6. Status Dashboard** | Web dashboard with live health stats, history & instant check | ✅ Working |
| **7. Alert System** | Background email alert dispatcher on failure or missing backups | ⏳ Weeks 9–10 |
| **8. CLI Utility** | Command-line management (ackup, erify, history, status) | ✅ Working |

---

## 🚀 Quickstart

### 1. Setup Environment
`ash
git clone https://github.com/adityabansal0999/BackupVault.git
cd BackupVault
pip install -r requirements.txt
cp .env.example .env   # Configure your DB_PASSWORD in .env
`

### 2. Initialize Database
`ash
mysql -u root -p < sql/schema_metadata.sql
mysql -u root -p < sql/schema_customer_db.sql
mysql -u root -p < sql/seed_customer_db.sql
`

### 3. Launch
`ash
# Start Web Dashboard & API (served at http://localhost:8000)
uvicorn backend.app.main:app --reload

# Or use CLI
python cli/backup_vault_cli.py status
`

---

## 💻 CLI Commands

| Command | Usage | Description |
|---|---|---|
| ackup | python cli/backup_vault_cli.py backup | Triggers an immediate snapshot |
| erify | python cli/backup_vault_cli.py verify <id> | Tests gzip & SHA-256 integrity |
| list | python cli/backup_vault_cli.py list | Displays recent backup entries |
| history| python cli/backup_vault_cli.py history | Detailed log with total storage footprint |
| status | python cli/backup_vault_cli.py status | System health summary |
| schedule| python cli/backup_vault_cli.py schedule | Runs foreground scheduler daemon |

---

## 👥 Team
- **Person A:** Backup & Restore Engine (mysqldump, compression, restore)
- **Person B:** Automation & Verification (APScheduler, auto-testing, alerts)
- **Person C:** Dashboard & CLI (FastAPI, Web UI, CLI tooling, docs)
