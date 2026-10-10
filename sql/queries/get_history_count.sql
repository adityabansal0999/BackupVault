SELECT COUNT(*) as total FROM backups WHERE 1=1 AND (%(date_from)s IS NULL OR created_at >= %(date_from)s) AND (%(date_to)s IS NULL OR created_at <= %(date_to)s)
