SELECT MAX(created_at)
FROM backups
WHERE status = 'SUCCESS';
