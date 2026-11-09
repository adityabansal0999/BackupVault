
SELECT
    (SELECT file_name
     FROM backups
     ORDER BY created_at DESC, backup_id DESC
     LIMIT 1) AS last_file,

    (SELECT status
     FROM backups
     ORDER BY created_at DESC, backup_id DESC
     LIMIT 1) AS last_status,

    (SELECT created_at
     FROM backups
     ORDER BY created_at DESC, backup_id DESC
     LIMIT 1) AS last_time,

    (SELECT COUNT(*)
     FROM backups
     WHERE status = 'SUCCESS') AS total,

    (SELECT COALESCE(SUM(file_size_bytes), 0)
     FROM backups
     WHERE status = 'SUCCESS') AS total_storage,

    (SELECT
        CASE
            WHEN COUNT(*) = 0 THEN NULL
            ELSE ROUND(
                100.0 * SUM(status = 'SUCCESS') / COUNT(*), 1
            )
        END
     FROM (
         SELECT status
         FROM backups
         ORDER BY created_at DESC, backup_id DESC
         LIMIT 20
     ) AS recent) AS success_rate,

    (SELECT COUNT(*)
     FROM (
         SELECT status
         FROM backups
         ORDER BY created_at DESC, backup_id DESC
         LIMIT 20
     ) AS recent_count) AS recent_count,

    (SELECT next_run_at
     FROM schedule_config
     WHERE id = 1) AS next_run_at,

    (SELECT cron_expression
     FROM schedule_config
     WHERE id = 1) AS cron_expression;
