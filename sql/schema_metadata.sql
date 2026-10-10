CREATE DATABASE IF NOT EXISTS backupvault_meta
CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;

USE backupvault_meta;
SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS=1;

CREATE TABLE schedule_config (
    id TINYINT UNSIGNED NOT NULL,
    cron_expression VARCHAR(64) NOT NULL DEFAULT '0 2 * * *',
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    retention_days INT UNSIGNED NOT NULL DEFAULT 90,
    next_run_at DATETIME NULL,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT chk_schedule_singleton CHECK (id=1)
) ENGINE=InnoDB;

INSERT INTO schedule_config (id, cron_expression, is_enabled, retention_days, next_run_at)
VALUES (1, '0 2 * * *', TRUE, 90, NULL)
ON DUPLICATE KEY UPDATE cron_expression=VALUES(cron_expression);

CREATE TABLE backups (
    backup_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    file_name VARCHAR(255) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    file_size_bytes BIGINT UNSIGNED NOT NULL DEFAULT 0,
    compressed_size_bytes BIGINT UNSIGNED NULL,
    checksum_sha256 CHAR(64) NULL,
    database_name VARCHAR(128) NOT NULL,
    backup_type ENUM('FULL') NOT NULL DEFAULT 'FULL',
    status ENUM('IN_PROGRESS','SUCCESS','FAILED') NOT NULL,
    verification_status ENUM('PENDING','PASS','FAIL') NOT NULL DEFAULT 'PENDING',
    restore_test_status ENUM('PENDING','PASS','FAIL','NOT_RUN') NOT NULL DEFAULT 'NOT_RUN',
    created_at DATETIME NOT NULL,
    completed_at DATETIME NULL,
    duration_seconds INT UNSIGNED NULL,
    error_message TEXT NULL,
    created_by VARCHAR(64) NOT NULL DEFAULT 'scheduler',
    PRIMARY KEY (backup_id),
    UNIQUE KEY uq_backups_file_name (file_name),
    INDEX idx_backups_created_at (created_at DESC),
    INDEX idx_backups_status (status),
    INDEX idx_backups_database (database_name)
) ENGINE=InnoDB;

CREATE TABLE backup_verifications (
    verification_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    backup_id BIGINT UNSIGNED NOT NULL,
    checked_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    result ENUM('PASS','FAIL') NOT NULL,
    file_exists BOOLEAN NOT NULL,
    file_size_ok BOOLEAN NOT NULL,
    gzip_valid BOOLEAN NOT NULL,
    checksum_match BOOLEAN NULL,
    details JSON NULL,
    PRIMARY KEY (verification_id),
    INDEX idx_verifications_backup (backup_id),
    CONSTRAINT fk_verifications_backup FOREIGN KEY (backup_id) REFERENCES backups(backup_id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE TABLE restore_tests (
    test_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    backup_id BIGINT UNSIGNED NOT NULL,
    test_db_name VARCHAR(128) NOT NULL,
    started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME NULL,
    row_count_original BIGINT UNSIGNED NULL,
    row_count_restored BIGINT UNSIGNED NULL,
    checksum_match BOOLEAN NULL,
    status ENUM('RUNNING','PASS','FAIL') NOT NULL DEFAULT 'RUNNING',
    error_message TEXT NULL,
    PRIMARY KEY (test_id),
    INDEX idx_restore_tests_backup (backup_id),
    INDEX idx_restore_tests_status (status),
    CONSTRAINT fk_restore_tests_backup FOREIGN KEY (backup_id) REFERENCES backups(backup_id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE TABLE restores (
    restore_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    backup_id BIGINT UNSIGNED NOT NULL,
    target_database VARCHAR(128) NOT NULL,
    restored_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    restored_by VARCHAR(64) NOT NULL DEFAULT 'cli',
    status ENUM('IN_PROGRESS','SUCCESS','FAILED') NOT NULL DEFAULT 'IN_PROGRESS',
    duration_seconds INT UNSIGNED NULL,
    error_message TEXT NULL,
    PRIMARY KEY (restore_id),
    INDEX idx_restores_backup (backup_id),
    INDEX idx_restores_restored_at (restored_at DESC),
    CONSTRAINT fk_restores_backup FOREIGN KEY (backup_id) REFERENCES backups(backup_id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE TABLE alert_log (
    alert_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    backup_id BIGINT UNSIGNED NULL,
    alert_type ENUM('BACKUP_FAILED','RESTORE_TEST_FAILED','NO_BACKUP_48H','STORAGE_HIGH') NOT NULL,
    message VARCHAR(500) NOT NULL,
    sent_to_email VARCHAR(255) NULL,
    is_sent BOOLEAN NOT NULL DEFAULT FALSE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (alert_id),
    INDEX idx_alert_created_at (created_at DESC),
    INDEX idx_alert_type (alert_type),
    INDEX idx_alert_backup (backup_id),
    CONSTRAINT fk_alert_backup FOREIGN KEY (backup_id) REFERENCES backups(backup_id) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB;