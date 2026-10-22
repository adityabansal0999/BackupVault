# BackupVault

> **Automated Backups, Integrity Verification & Monitoring System**  
> *Database Fundamentals Course — 12-Week University Project*

---

## 📌 Project Overview

**BackupVault** is an enterprise-grade automated backup and disaster-recovery solution designed for relational databases (MySQL/PostgreSQL). 

In production environments, unmonitored or unverified backups lead to silent disasters: corrupt dumps, missing tables, and unrecoverable data when outages occur. BackupVault solves this by automating off-peak snapshot creation, verifying backup file integrity with SHA-256 and decompression tests, cataloging complete metadata in an independent storage repository, and presenting real-time health metrics on a web dashboard and command-line interface.

---

## 🚀 Current Implementation Status (Weeks 1–6 Milestone)

As per the 12-week development roadmap, the project has currently completed **Phase 1 (Design & Architecture)** and the initial features of **Phase 2 (Core Engine, Verification & Dashboard)**:

| Feature | Scope / Requirements | Current Implementation Status |
|---|---|:---:|
| **1. Scheduled Backup Creation** | mysqldump integration, streaming gzip compression, SHA-256 checksum computation, timestamped files, APScheduler cron integration, metadata cataloging. | ✅ **Completed & Working** |
| **2. Backup Verification** | 4-step health verification: file existence check, minimum size threshold (>1KB), gzip validity test, and SHA-256 hash matching against stored metadata. | ✅ **Completed & Working** |
| **3. Backup History & Listing** | Comprehensive metadata queries, date-range filtering, cumulative byte storage calculation, and pagination. | ✅ **Completed & Working** |
| **4. Point-in-Time Restore** | Target database restoration from selected backup snapshot with mandatory confirmation safety check. | ⏳ *In Progress (Weeks 7–8)* |
| **5. Automated Restore Testing** | Automatic post-backup test restore to a disposable database, comparing table row counts and table checksums. | ⏳ *In Progress (Weeks 9–10)* |
| **6. Status Dashboard** | Responsive web dashboard displaying last backup status, next scheduled run, storage usage, success rate, filterable history table, manual trigger, and inline verification checks. | ✅ **Completed & Working** |
| **7. Alert System** | Background monitor and SMTP email dispatcher on backup failures, restore test failures, storage > 90%, and missing backups (>48h). | ⏳ *In Progress (Weeks 9–10)* |
| **8. Command Line Interface (CLI)** | Typer & Rich CLI supporting ackup, list, history, erify, status, and schedule execution. | ✅ **Working for Implemented Features** |

---

## 🏗️ System Architecture

`	ext
                     [ APScheduler (0 2 * * *) ]
                                 │
                 ┌───────────────┼───────────────┐
                 ▼               ▼               ▼
           [ Web Dashboard ]  [ CLI Tool ]  [ Background Daemon ]
                 │               │               │
                 └───────────────┼───────────────┘
                                 ▼
                     [ FastAPI Backend Engine ]
                                 │
        ┌────────────────────────┼────────────────────────┐
        ▼                                                 ▼
[ mysqldump --single-transaction ]              [ Metadata Catalog (MySQL) ]
        │                                         (backupvault_meta)
        ▼                                         ├── schedule_config
  [ gzip Stream ]                                 ├── backups
        │                                         ├── backup_verifications
        ├─── Compute SHA-256                      ├── restore_tests
        ▼                                         ├── restores
 [ Disk Storage: ./backups/*.sql.gz ]             └── alert_log
`

### Key Architectural Highlights:
1. **Zero Locking Snapshot:** Backups execute using mysqldump --single-transaction --quick, ensuring zero downtime or table locking on active production tables.
2. **Streaming Compression:** Standard output is piped straight into gzip in 1 MB chunks to prevent RAM exhaustion when handling multi-gigabyte databases.
3. **Storage Separation:** Actual backup .sql.gz files live strictly on the filesystem (./backups/). Only lightweight metadata (file path, file size, status, checksum) is stored in the database.
4. **Dedicated Metadata Catalog:** All audit history, verification records, and schedule configs are stored in an independent database (ackupvault_meta) using MySQL InnoDB with FOREIGN KEY ... ON DELETE RESTRICT constraints to prevent history deletion.

---

## 🗄️ Database Schemas

The system coordinates two distinct databases:

### 1. customer_db (Source / Target Database)
A representative e-commerce dataset containing:
- customers (customer_id, irst_name, last_name, email, country, created_at)
- orders (order_id, customer_id, order_total, status, ordered_at) with index on customer_id and foreign key cascade protection.

### 2. ackupvault_meta (Metadata & Audit Catalog)
- schedule_config — Singleton row (id=1) holding the active cron expression, retention days (default 90), and next run time.
- ackups — Central entity tracking every backup: file name, path, byte size, SHA-256 hash, duration, and status (IN_PROGRESS, SUCCESS, FAILED).
- ackup_verifications — Historical log of integrity checks: file presence, size validity, gzip stream readability, checksum match, and execution timestamp.
- estore_tests — (Schema ready) Dedicated table for automated disposable database restore validations.
- estores — (Schema ready) Audit trail of executed manual restorations.
- lert_log — Event log capturing failure notifications and system thresholds.

---

## ⚙️ Prerequisites & Setup Guide

### Prerequisites
- **Python 3.10+**
- **MySQL Server 8.0+**
- mysqldump installed and accessible in your system PATH.

---

### Step 1: Clone the Repository & Enter Directory
`ash
git clone https://github.com/adityabansal0999/BackupVault.git
cd BackupVault
`

### Step 2: Create a Virtual Environment & Install Dependencies
`ash
python -m venv venv

# Windows
.\venv\Scripts\activate

# Linux / macOS
source venv/bin/activate

# Install required dependencies
pip install -r requirements.txt
`

### Step 3: Configure Environment Variables
Copy .env.example to .env and fill in your MySQL credentials:
`ash
# Windows (PowerShell)
Copy-Item .env.example .env

# Linux / macOS
cp .env.example .env
`

Edit .env with your settings:
`ini
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_NAME=backupvault_meta
TARGET_DB_NAME=customer_db
BACKUP_DIR=./backups
ALERT_EMAIL=admin@company.com
CRON_EXPRESSION=0 2 * * *
SCHEDULER_TIMEZONE=Asia/Kolkata
`

### Step 4: Initialize MySQL Databases
Execute the SQL initialization scripts in MySQL:
`ash
# 1. Initialize metadata database schema & configuration
mysql -u root -p < sql/schema_metadata.sql

# 2. Initialize customer database schema & sample dataset
mysql -u root -p < sql/schema_customer_db.sql
mysql -u root -p < sql/seed_customer_db.sql
`

---

## 🖥️ Running BackupVault

### Option 1: Start the Web Dashboard & API
Start the FastAPI application:
`ash
uvicorn backend.app.main:app --reload --port 8000
`
- **Dashboard Interface:** Open your browser at http://localhost:8000 (automatically redirects to /dashboard).
- **Swagger API Documentation:** Explore interactive API docs at http://localhost:8000/docs.

### Option 2: Using the Command Line Interface (CLI)
You can operate BackupVault entirely from the terminal:

`ash
# Trigger an immediate on-demand backup
python cli/backup_vault_cli.py backup

# View current system status summary
python cli/backup_vault_cli.py status

# List recent backups
python cli/backup_vault_cli.py list

# View detailed backup history with total storage footprint
python cli/backup_vault_cli.py history

# Run an integrity verification check on backup #1
python cli/backup_vault_cli.py verify 1

# Start the foreground scheduler process
python cli/backup_vault_cli.py schedule
`

---

## 📡 REST API Reference (Working Endpoints)

| Method | Endpoint | Description |
|---|---|---|
| GET | / | Redirects directly to /dashboard. |
| GET | /api/status | Returns latest backup summary, cumulative storage, success rate %, and next scheduled run. |
| POST | /api/backups | Creates a new backup snapshot on-demand. |
| GET | /api/backups | Lists backups with pagination (limit, offset) and date filtering (date_from, date_to). |
| GET | /api/backups/history | Returns paginated items alongside total count and total byte storage. |
| POST | /api/backups/{id}/verify | Executes 4-point integrity check on backup {id} and records results. |
| GET | /api/backups/{id}/verifications | Retrieves verification history for backup {id}. |

---

## 👥 Team Work Allocation (12-Week Course Project)

- **Person A (Backup & Restore Engine):** Backup creation using mysqldump, streaming compression, metadata schema setup, and point-in-time restore logic.
- **Person B (Automation & Testing):** APScheduler scheduled backups, catch-up execution, automated restore test engine, and email alert dispatcher.
- **Person C (Dashboard & CLI):** Status monitoring web dashboard, Typer CLI commands, error handling, documentation, and demo verification.
