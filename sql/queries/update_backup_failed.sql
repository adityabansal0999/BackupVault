UPDATE backups
SET status = 'FAILED',
    completed_at = %s,
    duration_seconds = %s,
    error_message = %s
WHERE backup_id = %s;
