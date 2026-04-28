from datetime import datetime, timezone
import json
from typing import Dict, Optional

from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.db.models import (
    ForumPost,
    HomeworkRecord,
    LessonPlanRecord,
    MicrocourseAnalysis,
    NoticeRecord,
    TeacherStats,
    VisitRecord,
)


class TeacherStatsService:
    def __init__(self, db: Session, teacher_id: int) -> None:
        self.db = db
        self.teacher_id = teacher_id
        self._redis = None
        try:
            import redis  # type: ignore

            client = redis.from_url(settings.redis_url, decode_responses=True)
            client.ping()
            self._redis = client
        except Exception:
            self._redis = None

    def compute_all_stats(self, force_refresh: bool = True) -> Dict:
        if not force_refresh:
            cached = self._get_cache()
            if cached:
                return cached

        lesson_count = (
            self.db.query(LessonPlanRecord)
            .filter(LessonPlanRecord.teacher_id == self.teacher_id)
            .count()
        )
        micro_count = (
            self.db.query(MicrocourseAnalysis)
            .filter(MicrocourseAnalysis.teacher_id == self.teacher_id)
            .count()
        )
        visit_count = (
            self.db.query(VisitRecord)
            .filter(VisitRecord.teacher_id == self.teacher_id)
            .count()
        )
        homework_count = (
            self.db.query(HomeworkRecord)
            .filter(HomeworkRecord.homework_id.like(f"{self.teacher_id}_%"))
            .count()
        )
        forum_count = (
            self.db.query(ForumPost)
            .filter(ForumPost.author_id == self.teacher_id)
            .count()
        )

        dimensions = self._compute_dimensions()

        stats = (
            self.db.query(TeacherStats)
            .filter(TeacherStats.teacher_id == self.teacher_id)
            .first()
        )
        if not stats:
            stats = TeacherStats(teacher_id=self.teacher_id)
            self.db.add(stats)

        stats.total_lesson_plans = lesson_count
        stats.total_micro_analysis = micro_count
        stats.total_visit_records = visit_count
        stats.total_homework_batches = homework_count
        stats.total_forum_posts = forum_count
        stats.five_dimensions = dimensions
        stats.updated_at = datetime.now(timezone.utc)
        self.db.commit()

        payload = {
            "stats": {
                "total_lesson_plans": lesson_count,
                "total_micro_analysis": micro_count,
                "total_visit_records": visit_count,
                "total_homework_batches": homework_count,
                "total_forum_posts": forum_count,
            },
            "five_dimensions": dimensions,
        }
        self._set_cache(payload)
        return payload

    def _compute_dimensions(self) -> Dict[str, int]:
        visit_count = (
            self.db.query(VisitRecord)
            .filter(VisitRecord.teacher_id == self.teacher_id)
            .count()
        )
        notice_count = (
            self.db.query(NoticeRecord)
            .filter(NoticeRecord.teacher_id == self.teacher_id)
            .count()
        )
        communication = min((visit_count * 5) + (notice_count // 5), 100)

        micro_records = (
            self.db.query(MicrocourseAnalysis)
            .filter(MicrocourseAnalysis.teacher_id == self.teacher_id)
            .order_by(MicrocourseAnalysis.created_at.desc())
            .limit(5)
            .all()
        )
        intro = explain = practice_scaled = 50.0
        if micro_records:
            intro_avg = self._avg_score(micro_records, "intro", default=5.0)
            explain_avg = self._avg_score(micro_records, "explain", default=5.0)
            practice_avg = self._avg_score(micro_records, "practice", default=5.0)
            intro = intro_avg * 10
            explain = explain_avg * 10
            practice_scaled = practice_avg * 10

        homework_records = (
            self.db.query(HomeworkRecord)
            .filter(HomeworkRecord.homework_id.like(f"{self.teacher_id}_%"))
            .order_by(HomeworkRecord.created_at.desc())
            .limit(5)
            .all()
        )
        homework_quality = 60.0
        if homework_records:
            rates = []
            for hw in homework_records:
                summary = hw.summary_stats or {}
                total_students = int(summary.get("total_students", 0) or 0)
                correct_count = int(summary.get("correct_count", 0) or 0)
                if total_students > 0:
                    rates.append(correct_count / total_students)
            if rates:
                homework_quality = sum(rates) / len(rates) * 100

        forum_score = min(
            self.db.query(ForumPost).filter(ForumPost.author_id == self.teacher_id).count() * 2,
            30,
        )
        interaction = min(practice_scaled * 0.7 + forum_score, 100)

        return {
            "communication": round(communication),
            "intro": round(intro),
            "explain": round(explain),
            "homework_quality": round(homework_quality),
            "interaction": round(interaction),
        }

    @staticmethod
    def _avg_score(records: list, key: str, default: float) -> float:
        values = []
        for record in records:
            scores = record.scores or {}
            value = scores.get(key, default)
            try:
                values.append(float(value))
            except (TypeError, ValueError):
                values.append(default)
        return sum(values) / len(values) if values else default

    def get_cached_stats(self) -> Optional[TeacherStats]:
        return (
            self.db.query(TeacherStats)
            .filter(TeacherStats.teacher_id == self.teacher_id)
            .first()
        )

    def _cache_key(self) -> str:
        return f"teacher_growth:{self.teacher_id}"

    def _get_cache(self) -> Optional[Dict]:
        if not self._redis:
            return None
        try:
            value = self._redis.get(self._cache_key())
            if not value:
                return None
            data = json.loads(value)
            if isinstance(data, dict):
                return data
        except Exception:
            return None
        return None

    def _set_cache(self, payload: Dict) -> None:
        if not self._redis:
            return
        try:
            self._redis.setex(self._cache_key(), 300, json.dumps(payload, ensure_ascii=False))
        except Exception:
            pass
