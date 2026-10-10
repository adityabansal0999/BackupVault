USE backupvault_meta;

INSERT INTO schedule_config (id, cron_expression, is_enabled, retention_days, next_run_at)
VALUES (1, '0 2 * * *', TRUE, 90, NULL)
ON DUPLICATE KEY UPDATE cron_expression=VALUES(cron_expression), retention_days=VALUES(retention_days);

