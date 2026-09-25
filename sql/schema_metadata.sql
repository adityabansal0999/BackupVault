-- BackupVault metadata database schema (backupvault_meta)
-- matches Week1-2_Architecture_Plan_Tech_Stack_Schema.docx

CREATE DATABASE IF NOT EXISTS backupvault_meta;
USE backupvault_meta;

-- 1. backups, central table, one row per backup file
CREATE TABLE backups (
    backup_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    file_name VARCHAR(255) NOT NULL UNIQUE,
    file_path VARCHAR(500) NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    compressed_size BIGINT NULL,
    compression_type ENUM('gzip','bzip2') NULL DEFAULT 'gzip',
    checksum_sha256 CHAR(64) NULL,
    database_name VARCHAR(128) NOT NULL,
    backup_type ENUM('FULL','INCREMENTAL') NOT NULL DEFAULT 'FULL',
    status ENUM('IN_PROGRESS','SUCCESS','FAILED') NOT NULL,
    verification_status ENUM('PENDING','PASS','FAIL') NOT NULL DEFAULT 'PENDING',
    restore_test_status ENUM('PENDING','PASS','FAIL','NOT_RUN') NOT NULL DEFAULT 'NOT_RUN',
    created_at DATETIME NOT NULL,
    completed_at DATETIME NULL,
    duration_seconds INT NULL,
    error_message TEXT NULL,
    created_by VARCHAR(64) NOT NULL DEFAULT 'scheduler',
    INDEX idx_database_name (database_name),
    INDEX idx_status (status),
    INDEX idx_created_at (created_at DESC)
) ENGINE=InnoDB;

-- 2. schedule_config, singleton row, id is always 1
CREATE TABLE schedule_config (
    id TINYINT PRIMARY KEY CHECK (id = 1),
    cron_expression VARCHAR(64) NOT NULL,
    is_enabled BOOL NOT NULL DEFAULT 1,
    retention_days INT NOT NULL DEFAULT 30,
    next_run_at DATETIME NULL,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- 3. backup_verifications, history of checks, many per backup
CREATE TABLE backup_verifications (
    verification_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    backup_id BIGINT NOT NULL,
    checked_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    result ENUM('PASS','FAIL') NOT NULL,
    file_exists BOOL NOT NULL,
    file_size_ok BOOL NOT NULL,
    gzip_valid BOOL NOT NULL,
    checksum_match BOOL NULL,
    details JSON NULL,
    FOREIGN KEY (backup_id) REFERENCES backups(backup_id) ON DELETE RESTRICT
) ENGINE=InnoDB;

-- 4. restore_tests, automated restore tests, many per backup
CREATE TABLE restore_tests (
    test_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    backup_id BIGINT NOT NULL,
    test_db_name VARCHAR(128) NOT NULL,
    started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME NULL,
    row_count_original BIGINT NULL,
    row_count_restored BIGINT NULL,
    checksum_match BOOL NULL,
    status ENUM('RUNNING','PASS','FAIL') NOT NULL,
    error_message TEXT NULL,
    FOREIGN KEY (backup_id) REFERENCES backups(backup_id) ON DELETE RESTRICT,
    INDEX idx_status (status)
) ENGINE=InnoDB;

-- 5. restores, manual restores, many per backup
CREATE TABLE restores (
    restore_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    backup_id BIGINT NOT NULL,
    target_database VARCHAR(128) NOT NULL,
    restored_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    restored_by VARCHAR(64) NOT NULL DEFAULT 'cli',
    status ENUM('IN_PROGRESS','SUCCESS','FAILED') NOT NULL,
    duration_seconds INT NULL,
    error_message TEXT NULL,
    FOREIGN KEY (backup_id) REFERENCES backups(backup_id) ON DELETE RESTRICT,
    INDEX idx_restored_at (restored_at DESC)
) ENGINE=InnoDB;

-- 6. alert_log, alerts, backup_id is NULL for system level events
CREATE TABLE alert_log (
    alert_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    backup_id BIGINT NULL,
    alert_type ENUM('BACKUP_FAILED','RESTORE_TEST_FAILED','NO_BACKUP_48H','STORAGE_HIGH') NOT NULL,
    message VARCHAR(500) NOT NULL,
    sent_to_email VARCHAR(255) NOT NULL,
    is_sent BOOL NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (backup_id) REFERENCES backups(backup_id) ON DELETE RESTRICT,
    INDEX idx_alert_type (alert_type),
    INDEX idx_created_at (created_at DESC)
) ENGINE=InnoDB;

-- 7. backup_reports, V2, weekly summaries
CREATE TABLE backup_reports (
    report_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    total_backups INT NOT NULL,
    total_storage BIGINT NOT NULL,
    generated_at DATETIME NOT NULL,
    report_file VARCHAR(500) NOT NULL
) ENGINE=InnoDB;
