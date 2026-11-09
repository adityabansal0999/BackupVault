INSERT INTO backup_table_manifests (
    backup_id,
    table_name,
    row_count,
    checksum
)
VALUES (%s, %s, %s, %s);