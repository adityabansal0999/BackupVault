# runs create_backup() automatically on a cron schedule (default: 02:00 daily)
# apscheduler works out the next matching clock time from the cron string, sleeps until then,
# runs the job, then computes the following one. the python process has to stay running.
# two ways to run this: inside the api (main.py) or standalone with python -m cli.backup_vault_cli schedule
import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from backend.app import config
from backend.app.db import get_conn, load_sql
from backend.app.services.backup_service import create_backup

log = logging.getLogger("backupvault.scheduler")
JOB_ID = "scheduled_backup"


def _job_backup():
    # wrapper so one failed run never kills the scheduler
    try:
        result = create_backup(created_by="scheduler")
        log.info("Scheduled backup finished: %s", result)
    except Exception:
        log.exception("Scheduled backup crashed")


def _save_schedule_state(scheduler):
    # store cron + next run time in schedule_config so dashboard/status can show "next backup"
    job = scheduler.get_job(JOB_ID)
    next_run = job.next_run_time.astimezone().replace(tzinfo=None) if job and job.next_run_time else None
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(load_sql("upsert_schedule_config"), (config.CRON_EXPRESSION, config.RETENTION_DAYS, next_run))
    conn.commit()
    cur.close()
    conn.close()


def _catch_up_needed():
    # true if theres no SUCCESS backup newer than CATCH_UP_HOURS (app was off at backup time)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(load_sql("get_last_success_backup"))
    last = cur.fetchone()[0]
    cur.close()
    conn.close()
    return last is None or last < datetime.now() - timedelta(hours=config.CATCH_UP_HOURS)


def _configure(scheduler):
    trigger = CronTrigger.from_crontab(config.CRON_EXPRESSION, timezone=config.SCHEDULER_TIMEZONE)
    scheduler.add_job(
        _job_backup, trigger, id=JOB_ID, replace_existing=True,
        max_instances=1,  # never two backups at the same time
        coalesce=True,  # if several runs were missed, run only once
        misfire_grace_time=3600,  # still run if we wake up up to 1h late
    )
    # after every run, refresh next_run_at in the db
    from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
    scheduler.add_listener(lambda e: _save_schedule_state(scheduler), EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)


def start_scheduler():
    # non blocking, used by fastapi startup
    scheduler = BackgroundScheduler(timezone=config.SCHEDULER_TIMEZONE)
    _configure(scheduler)
    scheduler.start()
    _save_schedule_state(scheduler)
    if _catch_up_needed():
        log.warning("No recent backup found - running a catch-up backup now")
        scheduler.add_job(_job_backup, id="catch_up", replace_existing=True)  # runs immediately
    log.info("Scheduler started: '%s' (%s), next run %s", config.CRON_EXPRESSION, config.SCHEDULER_TIMEZONE, scheduler.get_job(JOB_ID).next_run_time)
    return scheduler


def run_blocking():
    # blocking, used by the cli "schedule" command (keeps running until ctrl+c)
    scheduler = BlockingScheduler(timezone=config.SCHEDULER_TIMEZONE)
    _configure(scheduler)
    scheduler.add_job(lambda: _save_schedule_state(scheduler), id="init_state")
    if _catch_up_needed():
        scheduler.add_job(_job_backup, id="catch_up")
    log.info("Scheduler running: '%s' (%s). Ctrl+C to stop.", config.CRON_EXPRESSION, config.SCHEDULER_TIMEZONE)
    scheduler.start()
