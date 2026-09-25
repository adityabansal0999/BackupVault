INSERT INTO backups (file_name, file_path, file_size_bytes, checksum_sha256, database_name, status, created_at)
VALUES (%s, %s, %s, %s, %s, %s, %s);
