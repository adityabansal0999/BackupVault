SELECT COUNT(*)
FROM alert_log a
WHERE a.alert_type = 'NO_BACKUP_48H'
  AND a.created_at > COALESCE(
      (
          SELECT MAX(completed_at)
          FROM backups
          WHERE status = 'SUCCESS'
      ),
      '1000-01-01 00:00:00'
  );