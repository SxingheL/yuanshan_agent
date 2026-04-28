try:
    from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore
except Exception:
    BackgroundScheduler = None  # type: ignore

from backend.app.db.database import SessionLocal
from backend.app.services.student_archive import StudentArchiveService


_scheduler = None


def start_student_archive_scheduler() -> None:
    global _scheduler
    if BackgroundScheduler is None:
        return
    if _scheduler and _scheduler.running:
        return

    scheduler = BackgroundScheduler(timezone="Asia/Shanghai")

    def _refresh_stats() -> None:
        db = SessionLocal()
        try:
            StudentArchiveService(db).refresh_all_stats()
        finally:
            db.close()

    scheduler.add_job(_refresh_stats, "cron", hour=2, minute=0, id="student_archive_stats")
    scheduler.start()
    _scheduler = scheduler
