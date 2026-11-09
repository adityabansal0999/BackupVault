
import logging
import shutil
import smtplib
import ssl

from datetime import datetime, timedelta
from email.message import EmailMessage
from pathlib import Path

from backend.app import config
from backend.app.db import get_conn, load_sql


logger = logging.getLogger("backupvault.alerts")


ALLOWED_ALERT_TYPES = {
    "BACKUP_FAILED",
    "RESTORE_TEST_FAILED",
    "NO_BACKUP_48H",
    "STORAGE_HIGH",
}


# ============================================================
# CREATE ALERT
# ============================================================

def create_alert(
    alert_type,
    message,
    backup_id=None,
    recipient=None,
):
    """Insert a new alert into alert_log."""

    if alert_type not in ALLOWED_ALERT_TYPES:
        raise ValueError(
            f"Unsupported alert type: {alert_type}"
        )

    conn = get_conn()

    try:
        cur = conn.cursor()

        try:
            cur.execute(
                load_sql("insert_alert"),
                (
                    backup_id,
                    alert_type,
                    str(message)[:500],
                    recipient or config.ALERT_EMAIL,
                ),
            )

            alert_id = cur.lastrowid
            conn.commit()

            logger.warning(
                "Alert created: ID=%s, type=%s",
                alert_id,
                alert_type,
            )

            return alert_id

        finally:
            cur.close()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


# ============================================================
# EMAIL DELIVERY
# ============================================================

def _send_email(alert):
    """Send one alert using configured SMTP settings."""

    if not config.SMTP_HOST:
        raise RuntimeError(
            "SMTP_HOST is not configured in .env."
        )

    recipient = alert.get("sent_to_email")

    if not recipient:
        raise ValueError(
            "Alert does not have a recipient email address."
        )

    sender = (
        config.SMTP_FROM_EMAIL
        or config.SMTP_USERNAME
    )

    if not sender:
        raise RuntimeError(
            "SMTP_FROM_EMAIL or SMTP_USERNAME must be configured."
        )

    message = EmailMessage()

    message["Subject"] = (
        f"[BackupVault] {alert['alert_type']}"
    )

    message["From"] = sender
    message["To"] = recipient

    message.set_content(
        f"""
BackupVault Alert

Alert ID: {alert['alert_id']}
Alert Type: {alert['alert_type']}
Backup ID: {alert['backup_id']}

Message:
{alert['message']}

Created At:
{alert['created_at']}

Please inspect BackupVault for further details.
"""
    )

    context = ssl.create_default_context()

    if config.SMTP_USE_SSL:
        with smtplib.SMTP_SSL(
            config.SMTP_HOST,
            config.SMTP_PORT,
            timeout=20,
            context=context,
        ) as server:

            if config.SMTP_USERNAME:
                server.login(
                    config.SMTP_USERNAME,
                    config.SMTP_PASSWORD,
                )

            refused = server.send_message(message)

    else:
        with smtplib.SMTP(
            config.SMTP_HOST,
            config.SMTP_PORT,
            timeout=20,
        ) as server:

            server.ehlo()

            if config.SMTP_USE_TLS:
                server.starttls(context=context)
                server.ehlo()

            if config.SMTP_USERNAME:
                server.login(
                    config.SMTP_USERNAME,
                    config.SMTP_PASSWORD,
                )

            refused = server.send_message(message)

    if refused:
        raise RuntimeError(
            f"SMTP refused recipients: {refused}"
        )


# ============================================================
# MARK EMAIL AS SENT
# ============================================================

def _mark_alert_sent(alert_id):
    """Update is_sent only after successful email delivery."""

    conn = get_conn()

    try:
        cur = conn.cursor()

        try:
            cur.execute(
                load_sql("mark_alert_sent"),
                (alert_id,),
            )

            conn.commit()

        finally:
            cur.close()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


# ============================================================
# SEND PENDING ALERTS
# ============================================================

def send_pending_alerts(limit=100):
    """
    Send unsent alerts.

    Failed email deliveries remain is_sent = 0
    so a later monitoring cycle can retry them.
    """

    conn = get_conn()

    try:
        cur = conn.cursor(dictionary=True)

        try:
            cur.execute(
                load_sql("get_pending_alerts"),
                (limit,),
            )

            alerts = cur.fetchall()

        finally:
            cur.close()

    finally:
        conn.close()

    sent = 0
    failed = 0

    for alert in alerts:

        try:
            _send_email(alert)

            _mark_alert_sent(alert["alert_id"])

            sent += 1

            logger.info(
                "Alert email sent successfully: ID=%s",
                alert["alert_id"],
            )

        except Exception:
            failed += 1

            logger.exception(
                "Could not deliver alert email ID=%s. "
                "It remains pending.",
                alert["alert_id"],
            )

    return {
        "checked": len(alerts),
        "sent": sent,
        "failed": failed,
    }


# ============================================================
# NO BACKUP FOR 48 HOURS
# ============================================================

def _check_no_backup_alert():
    """Create one alert for the current 48-hour backup gap."""

    conn = get_conn()

    try:
        cur = conn.cursor()

        try:
            cur.execute(
                load_sql("get_last_success_backup")
            )

            row = cur.fetchone()
            last_backup = row[0] if row else None

            if (
                last_backup is not None
                and last_backup >= datetime.now() - timedelta(
                    hours=config.NO_BACKUP_ALERT_HOURS
                )
            ):
                return False

            cur.execute(
                load_sql("check_no_backup_alert")
            )

            existing = cur.fetchone()[0]

            if existing:
                return False

            create_alert(
                "NO_BACKUP_48H",
                (
                    f"No successful database backup has been "
                    f"recorded for at least "
                    f"{config.NO_BACKUP_ALERT_HOURS} hours."
                ),
            )

            return True

        finally:
            cur.close()

    finally:
        conn.close()


# ============================================================
# BACKUP STORAGE MONITOR
# ============================================================

def _check_storage_alert():
    """Monitor the disk containing the backup directory."""

    backup_path = Path(config.BACKUP_DIR).resolve()

    check_path = (
        backup_path
        if backup_path.exists()
        else backup_path.parent
    )

    usage = shutil.disk_usage(check_path)

    used_percent = (
        usage.used / usage.total
    ) * 100

    threshold = config.STORAGE_ALERT_THRESHOLD_PERCENT

    if used_percent <= threshold:
        return False

    # Avoid sending the same storage alert repeatedly.
    cooldown_start = datetime.now() - timedelta(
        hours=config.STORAGE_ALERT_COOLDOWN_HOURS
    )

    conn = get_conn()

    try:
        cur = conn.cursor()

        try:
            cur.execute(
                load_sql("check_storage_alert_since"),
                (cooldown_start,),
            )

            existing = cur.fetchone()[0]

            if existing:
                return False

        finally:
            cur.close()

    finally:
        conn.close()

    free_gb = usage.free / (1024 ** 3)

    create_alert(
        "STORAGE_HIGH",
        (
            f"Backup storage disk usage is "
            f"{used_percent:.2f}%, above the configured "
            f"{threshold:.2f}% threshold. "
            f"Free space: {free_gb:.2f} GiB."
        ),
    )

    return True


# ============================================================
# ALERT MONITOR
# ============================================================

def monitor_alert_conditions():
    """Check time-based and storage-based alert conditions."""

    created = []

    try:
        if _check_no_backup_alert():
            created.append("NO_BACKUP_48H")

    except Exception:
        logger.exception(
            "Could not check the 48-hour backup condition."
        )

    try:
        if _check_storage_alert():
            created.append("STORAGE_HIGH")

    except Exception:
        logger.exception(
            "Could not check backup storage usage."
        )

    # Deliver both newly created and previously pending alerts.
    delivery = send_pending_alerts()

    return {
        "alerts_created": created,
        "delivery": delivery,
    }
