UPDATE restores
SET
    status = 'FAILED',
    duration_seconds = %s,
    error_message = %s
WHERE restore_id = %s;