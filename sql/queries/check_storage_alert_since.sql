SELECT COUNT(*)
FROM alert_log
WHERE alert_type = 'STORAGE_HIGH'
  AND created_at >= %s;