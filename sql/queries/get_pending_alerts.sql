SELECT
    alert_id,
    backup_id,
    alert_type,
    message,
    sent_to_email,
    created_at
FROM alert_log
WHERE is_sent = 0
ORDER BY created_at ASC
LIMIT %s;