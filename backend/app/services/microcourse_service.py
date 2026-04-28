import uuid
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from backend.app.db.database import SessionLocal
from backend.app.db.models import MicrocourseAnalysis
from backend.app.services.comparison_engine import ComparisonEngine
from backend.app.services.master_matcher import MasterMatcher
from backend.app.services.video_processor import VideoProcessor


class MicrocourseTaskStore:
    _tasks: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def set(cls, task_id: str, payload: Dict[str, Any]) -> None:
        cls._tasks[task_id] = payload

    @classmethod
    def get(cls, task_id: str) -> Dict[str, Any]:
        return cls._tasks.get(task_id, {})


class MicrocourseService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.video_processor = VideoProcessor()
        self.comparison_engine = ComparisonEngine()
        self.matcher = MasterMatcher(db)

    @staticmethod
    def generate_task_id() -> str:
        return f"mc_{uuid.uuid4().hex[:8]}"

    def process_task(
        self,
        task_id: str,
        video_payload: Dict[str, Any],
        teacher_id: int,
        subject: str,
        grade: str,
        topic: str,
    ) -> None:
        try:
            transcript = self.video_processor.extract_transcript(
                video_bytes=video_payload["content"],
                filename=video_payload.get("filename", "lesson.mp4"),
            )
            master = self.matcher.match(subject=subject, grade=grade, topic=topic)
            comparison = self.comparison_engine.compare(
                teacher_text=transcript,
                master_text=master.get("transcript") or "",
            )
            scores = self._build_scores(comparison)
            self.db.add(
                MicrocourseAnalysis(
                    teacher_id=teacher_id,
                    subject=subject,
                    grade=grade,
                    topic=topic,
                    scores=scores,
                    summary=(comparison.get("structure_advice", "") or "")[:1000],
                )
            )
            self.db.commit()
            result = {
                "status": "completed",
                "teacher_transcript": transcript[:1800],
                "master_lesson": {
                    "title": master["title"],
                    "url": master["url"],
                    "grade": master.get("grade", grade),
                    "subject": master.get("subject", subject),
                    "similarity": master.get("similarity", 0),
                },
                "comparison": comparison,
                "scores": scores,
                "master_link_button": {
                    "text": "📺 观看名师完整公开课",
                    "url": master["url"],
                },
            }
            MicrocourseTaskStore.set(task_id, result)
        except Exception as e:
            MicrocourseTaskStore.set(
                task_id,
                {
                    "status": "failed",
                    "error": str(e),
                },
            )

    @staticmethod
    def _build_scores(comparison: Dict[str, Any]) -> Dict[str, float]:
        improvements = comparison.get("specific_improvements") or []
        if not isinstance(improvements, list):
            improvements = []
        improve_count = len(improvements)
        intro = max(5.5, 8.8 - improve_count * 0.25)
        explain = max(5.0, 8.4 - improve_count * 0.2)
        practice = max(4.8, 8.0 - improve_count * 0.2)
        summary = max(4.5, 7.6 - improve_count * 0.2)
        return {
            "intro": round(intro, 1),
            "explain": round(explain, 1),
            "practice": round(practice, 1),
            "summary": round(summary, 1),
        }


def run_microcourse_task(
    task_id: str,
    video_payload: Dict[str, Any],
    teacher_id: int,
    subject: str,
    grade: str,
    topic: str,
) -> None:
    db = SessionLocal()
    try:
        svc = MicrocourseService(db)
        svc.process_task(task_id, video_payload, teacher_id, subject, grade, topic)
    finally:
        db.close()
