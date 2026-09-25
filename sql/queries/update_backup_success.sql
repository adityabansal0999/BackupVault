UPDATE backups
SET file_size_bytes = %s,
    compressed_size = %s,
    compression_type = 'gzip',
    checksum_sha256 = %s,
    status = 'SUCCESS',
    completed_at = %s,
    duration_seconds = %s
WHERE backup_id = %s;
