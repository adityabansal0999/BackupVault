UPDATE restores
SET
    status = 'SUCCESS',
    duration_seconds = %s,
    error_message = NULL
WHERE restore_id = %s;