SELECT backup_id, file_name, file_path, file_size_bytes, status, verification_status, created_at
FROM backups
WHERE (%(date_from)s IS NULL OR created_at >= %(date_from)s)
AND (%(date_to)s IS NULL OR created_at <= %(date_to)s)
ORDER BY created_at DESC
LIMIT %(limit)s OFFSET %(offset)s;
