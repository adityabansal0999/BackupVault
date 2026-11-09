UPDATE alert_log
SET is_sent = 1
WHERE alert_id = %s
  AND is_sent = 0;