
import os
import gzip
import hashlib
import hmac
import zlib
from datetime import datetime

from backend.app.db import get_conn, load_sql


def _check_gzip_valid(path):
    """Validate the complete gzip stream, not just its first byte."""
    try:
        with gzip.open(path, "rb") as gz_file:
            while gz_file.read(1024 * 1024):
                pass
        return True
    except (OSError, EOFError, zlib.error):
        return False


def _checksum_match(path, stored):
    """Compare the complete file's SHA-256 against the stored checksum."""
    if not stored:
        return False

    stored = str(stored).strip()

    # SHA-256 hexadecimal checksums must contain exactly 64 characters.
    if len(stored) != 64:
        return False

    try:
        bytes.fromhex(stored)
    except ValueError:
        return False

    try:
        hasher = hashlib.sha256()

        with open(path, "rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                hasher.update(chunk)

        return hmac.compare_digest(
            hasher.hexdigest(),
            stored.lower()
        )
    except OSError:
        return False


def verify_backup(backup_id):
    conn = get_conn()

    try:
        # 1. Retrieve backup metadata from MySQL.
        cur = conn.cursor(dictionary=True)

        try:
            cur.execute(
                load_sql("get_backup_by_id"),
                (backup_id,)
            )
            row = cur.fetchone()
        finally:
            cur.close()

        if not row:
            return {
                "backup_id": backup_id,
                "result": "FAIL",
                "error": "Backup not found"
            }

        path = row["file_path"]

        # 2. Check whether the actual backup file exists.
        file_exists = bool(path) and os.path.isfile(path)

        file_size_ok = False
        gzip_valid = False
        checksum_ok = None
        actual_size = None

        if file_exists:
            # 3. Compare actual size with the recorded compressed size.
            try:
                actual_size = os.path.getsize(path)

                expected_size = row.get("compressed_size_bytes")

                # Fallback for older records without compressed_size_bytes.
                if expected_size is None:
                    expected_size = row.get("file_size_bytes")

                if expected_size is not None:
                    file_size_ok = (
                        actual_size == int(expected_size)
                    )
            except (OSError, TypeError, ValueError):
                file_size_ok = False

            # 4. Validate the entire compressed gzip stream.
            gzip_valid = _check_gzip_valid(path)

            # 5. Compare SHA-256 with the stored checksum.
            # A missing or invalid checksum results in False.
            checksum_ok = _checksum_match(
                path,
                row.get("checksum_sha256")
            )

        # 6. PASS only if every required check succeeds.
        result = (
            "PASS"
            if (
                file_exists
                and file_size_ok
                and gzip_valid
                and checksum_ok is True
            )
            else "FAIL"
        )

        checked_at = datetime.now()

        # 7. Save verification history and update backup status.
        cur = conn.cursor()

        try:
            cur.execute(
                load_sql("insert_verification"),
                (
                    backup_id,
                    checked_at,
                    result,
                    file_exists,
                    file_size_ok,
                    gzip_valid,
                    checksum_ok
                )
            )

            cur.execute(
                load_sql("update_verification_status"),
                (result, backup_id)
            )

            conn.commit()
        finally:
            cur.close()

        return {
            "backup_id": backup_id,
            "result": result,
            "file_exists": file_exists,
            "file_size_ok": file_size_ok,
            "gzip_valid": gzip_valid,
            "checksum_match": checksum_ok,
            "actual_size_bytes": actual_size,
            "checked_at": checked_at.isoformat()
        }

    finally:
        conn.close()
