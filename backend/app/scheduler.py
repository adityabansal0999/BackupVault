
import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from backend.app import config
from backend.app.db import get_conn, load_sql
from backend.app.services.backup_service import create_backup


log = logging.getLogger("backupvault.scheduler")

JOB_ID = "scheduled_backup"
ALERT_JOB_ID = "alert_monitor"


# ============================================================
# SCHEDULED BACKUP
# ============================================================

def _job_backup():
    """Run a scheduled backup without stopping the scheduler."""

    try:
        result = create_backup(created_by="scheduler")

        log.info(
            "Scheduled backup finished: %s",
            result,
        )

    except Exception:
        log.exception("Scheduled backup crashed.")


# ============================================================
# ALERT MONITOR
# ============================================================

def _job_alert_monitor():
    """Periodically check and deliver pending alerts."""

    try:
        from backend.app.services.alert_service import (
            monitor_alert_conditions,
        )

        result = monitor_alert_conditions()

        log.info(
            "Alert monitoring finished: %s",
            result,
        )

    except Exception:
        log.exception("Alert monitoring failed.")


# ============================================================
# SAVE SCHEDULE STATE
# ============================================================

def _save_schedule_state(scheduler):
    """Save the configured cron and next run time."""

    conn = None
    cur = None

    try:
        job = scheduler.get_job(JOB_ID)

        next_run = (
            job.next_run_time.astimezone().replace(tzinfo=None)
            if job and job.next_run_time
            else None
        )

        conn = get_conn()
        cur = conn.cursor()

        cur.execute(
            load_sql("upsert_schedule_config"),
            (
                config.CRON_EXPRESSION,
                config.RETENTION_DAYS,
                next_run,
            ),
        )

        conn.commit()

    except Exception:
        if conn:
            conn.rollback()

        log.exception("Could not save scheduler state.")

    finally:
        if cur:
            cur.close()

        if conn:
            conn.close()


# ============================================================
# CATCH-UP BACKUP CHECK
# ============================================================

def _catch_up_needed():
    """Check whether a recent successful backup exists."""

    conn = get_conn()
    cur = None

    try:
        cur = conn.cursor()

        cur.execute(
            load_sql("get_last_success_backup")
        )

        row = cur.fetchone()

        last_backup = row[0] if row else None

        return (
            last_backup is None
            or last_backup
            < datetime.now() - timedelta(
                hours=config.CATCH_UP_HOURS
            )
        )

    finally:
        if cur:
            cur.close()

        conn.close()


# ============================================================
# SCHEDULER CONFIGURATION
# ============================================================

def _configure(scheduler):
    """Register backup and alert-monitoring jobs."""

    # Daily or configured cron backup.
    trigger = CronTrigger.from_crontab(
        config.CRON_EXPRESSION,
        timezone=config.SCHEDULER_TIMEZONE,
    )

    scheduler.add_job(
        _job_backup,
        trigger,
        id=JOB_ID,
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )

    # Periodic alert monitoring.
    alert_interval = IntervalTrigger(
        minutes=config.ALERT_MONITOR_INTERVAL_MINUTES,
        timezone=config.SCHEDULER_TIMEZONE,
    )

    scheduler.add_job(
        _job_alert_monitor,
        alert_interval,
        id=ALERT_JOB_ID,
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )

    # Update the stored next backup time after backup execution.
    from apscheduler.events import (
        EVENT_JOB_EXECUTED,
        EVENT_JOB_ERROR,
    )

    def schedule_listener(event):
        if event.job_id == JOB_ID:
            _save_schedule_state(scheduler)

    scheduler.add_listener(
        schedule_listener,
        EVENT_JOB_EXECUTED | EVENT_JOB_ERROR,
    )


# ============================================================
# FASTAPI BACKGROUND SCHEDULER
# ============================================================

def start_scheduler():
    """Start scheduler in the background for FastAPI."""

    scheduler = BackgroundScheduler(
        timezone=config.SCHEDULER_TIMEZONE
    )

    _configure(scheduler)

    scheduler.start()

    _save_schedule_state(scheduler)

    if _catch_up_needed():
        log.warning(
            "No recent backup found. Running catch-up backup."
        )

        scheduler.add_job(
            _job_backup,
            id="catch_up",
            replace_existing=True,
        )

    log.info(
        "Scheduler started: %s (%s), next backup: %s",
        config.CRON_EXPRESSION,
        config.SCHEDULER_TIMEZONE,
        scheduler.get_job(JOB_ID).next_run_time,
    )

    log.info(
        "Alert monitoring interval: every %s minutes.",
        config.ALERT_MONITOR_INTERVAL_MINUTES,
    )

    return scheduler


# ============================================================
# BLOCKING CLI SCHEDULER
# ============================================================

def run_blocking():
    """Run the scheduler in blocking CLI mode."""

    scheduler = BlockingScheduler(
        timezone=config.SCHEDULER_TIMEZONE
    )

    _configure(scheduler)

    scheduler.add_job(
        lambda: _save_schedule_state(scheduler),
        id="init_state",
    )

    if _catch_up_needed():
        scheduler.add_job(
            _job_backup,
            id="catch_up",
        )

    log.info(
        "Scheduler running: %s (%s). Press Ctrl+C to stop.",
        config.CRON_EXPRESSION,
        config.SCHEDULER_TIMEZONE,
    )

    log.info(
        "Alert monitoring interval: every %s minutes.",
        config.ALERT_MONITOR_INTERVAL_MINUTES,
    )

    scheduler.start()
