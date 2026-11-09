INSERT INTO restores (
    backup_id,
    target_database,
    restored_by,
    status
)
VALUES (%s, %s, %s, 'IN_PROGRESS');