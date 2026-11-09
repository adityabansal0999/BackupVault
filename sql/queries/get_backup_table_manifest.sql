SELECT
    table_name,
    row_count,
    checksum
FROM backup_table_manifests
WHERE backup_id = %s
ORDER BY table_name;