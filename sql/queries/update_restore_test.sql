UPDATE restore_tests
SET
    completed_at = NOW(),
    row_count_original = %s,
    row_count_restored = %s,
    checksum_match = %s,
    status = %s,
    error_message = %s
WHERE test_id = %s;