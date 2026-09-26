"""
In-process scheduler for the Daily Report email — the lighter of the two
options from the plan (vs. Celery + Redis). Deliberately opt-in
(DAYBOOK_ENABLE_SCHEDULER=1), never auto-started.
"""
import logging
import os

logger = logging.getLogger(__name__)

_started = False


def _run_daily_report_check():
    from django.core.management import call_command
    try:
        call_command('send_daily_reports')
    except Exception:
        logger.exception('send_daily_reports failed')


def start():
    global _started
    if _started:
        return

    if os.environ.get('DAYBOOK_ENABLE_SCHEDULER') != '1':
        return

    if 'RUN_MAIN' in os.environ and os.environ.get('RUN_MAIN') != 'true':
        return

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except ImportError:
        logger.warning(
            "DAYBOOK_ENABLE_SCHEDULER=1 but APScheduler isn't installed — "
            "run: pip install APScheduler"
        )
        return

    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(
        _run_daily_report_check, 'interval', minutes=5,
        id='daybook_daily_report_check', replace_existing=True,
    )
    scheduler.start()
    _started = True
    logger.info('Daybook daily-report scheduler started (checks every 5 minutes).')
