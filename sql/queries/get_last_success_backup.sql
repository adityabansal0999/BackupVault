SELECT MAX(completed_at)
FROM backups
WHERE status = 'SUCCESS';