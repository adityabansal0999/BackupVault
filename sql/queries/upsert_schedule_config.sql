INSERT INTO schedule_config (id, cron_expression, is_enabled, retention_days, next_run_at, updated_at)
VALUES (1, %s, 1, %s, %s, NOW())
ON DUPLICATE KEY UPDATE
    cron_expression = VALUES(cron_expression),
    next_run_at = VALUES(next_run_at),
    updated_at = NOW();
