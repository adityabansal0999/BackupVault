INSERT INTO alert_log (backup_id, alert_type, message, sent_to_email, is_sent, created_at)
VALUES (%s, 'BACKUP_FAILED', %s, %s, 0, %s);
