SELECT
    (SELECT file_name FROM backups ORDER BY created_at DESC LIMIT 1) AS last_file,
    (SELECT status FROM backups ORDER BY created_at DESC LIMIT 1) AS last_status,
    (SELECT created_at FROM backups ORDER BY created_at DESC LIMIT 1) AS last_time,
    (SELECT SUM(file_size_bytes) FROM backups WHERE status = 'SUCCESS') AS total_storage,
    (SELECT 100.0 * SUM(status = 'SUCCESS') / COUNT(*) FROM backups) AS success_rate,
    (SELECT next_run_at FROM schedule_config WHERE id = 1) AS next_run_at,
    (SELECT cron_expression FROM schedule_config WHERE id = 1) AS cron_expression
FROM backups
LIMIT 1;
