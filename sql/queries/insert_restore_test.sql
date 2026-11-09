INSERT INTO restore_tests (
    backup_id,
    test_db_name,
    status
)
VALUES (%s, %s, 'RUNNING');