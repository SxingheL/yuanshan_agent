try:
    from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore
except Exception:
    BackgroundScheduler = None  # type: ignore

from backend.app.db.database import SessionLocal
from backend.app.services.psychology_service import (
    refresh_daily_reminder_for_all,
    refresh_weekly_list_for_all,
)


_scheduler = None


def start_psychology_scheduler() -> None:
    global _scheduler
    if BackgroundScheduler is None:
        return
    if _scheduler and _scheduler.running:
        return

    scheduler = BackgroundScheduler(timezone="Asia/Shanghai")

    def _daily_job() -> None:
        db = SessionLocal()
        try:
            refresh_daily_reminder_for_all(db)
        finally:
            db.close()

    def _weekly_job() -> None:
        db = SessionLocal()
        try:
            refresh_weekly_list_for_all(db)
        finally:
            db.close()

    scheduler.add_job(_daily_job, "cron", hour=6, minute=0, id="psychology_daily")
    scheduler.add_job(_weekly_job, "cron", day_of_week="mon", hour=6, minute=10, id="psychology_weekly")
    scheduler.start()
    _scheduler = scheduler
