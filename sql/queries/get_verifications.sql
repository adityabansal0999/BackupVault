SELECT verification_id, backup_id, checked_at, result, file_exists, file_size_ok, gzip_valid, checksum_match FROM backup_verifications WHERE backup_id = %s ORDER BY checked_at DESC LIMIT %s
