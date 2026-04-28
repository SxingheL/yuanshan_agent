from datetime import datetime, timezone
from typing import Dict, List

from sqlalchemy.orm import Session

from backend.app.db.models import BadgeDefinition, TeacherBadge, TeacherStats


class BadgeService:
    def __init__(self, db: Session, teacher_id: int) -> None:
        self.db = db
        self.teacher_id = teacher_id

    def check_and_update_badges(self) -> List[Dict]:
        stats = (
            self.db.query(TeacherStats)
            .filter(TeacherStats.teacher_id == self.teacher_id)
            .first()
        )
        if not stats:
            return []

        earned_rows = (
            self.db.query(TeacherBadge)
            .filter(TeacherBadge.teacher_id == self.teacher_id)
            .all()
        )
        earned_ids = {row.badge_id for row in earned_rows}
        definitions = (
            self.db.query(BadgeDefinition)
            .filter(BadgeDefinition.is_active.is_(True))
            .all()
        )

        new_badges: List[Dict] = []
        for badge in definitions:
            if badge.id in earned_ids:
                continue
            if self._check_condition(stats, badge):
                row = TeacherBadge(
                    teacher_id=self.teacher_id,
                    badge_id=badge.id,
                    badge_name=badge.name,
                    earned_at=datetime.now(timezone.utc),
                )
                self.db.add(row)
                new_badges.append(
                    {"id": badge.id, "name": badge.name, "icon": badge.icon_emoji}
                )
        self.db.commit()
        return new_badges

    def get_user_badges_with_progress(self) -> List[Dict]:
        stats = (
            self.db.query(TeacherStats)
            .filter(TeacherStats.teacher_id == self.teacher_id)
            .first()
        )
        if not stats:
            return []

        definitions = (
            self.db.query(BadgeDefinition)
            .filter(BadgeDefinition.is_active.is_(True))
            .all()
        )
        earned_rows = (
            self.db.query(TeacherBadge)
            .filter(TeacherBadge.teacher_id == self.teacher_id)
            .all()
        )
        earned_map = {row.badge_id: row for row in earned_rows}
        result: List[Dict] = []

        for badge in definitions:
            if badge.id in earned_map:
                row = earned_map[badge.id]
                result.append(
                    {
                        "id": badge.id,
                        "name": badge.name,
                        "description": badge.description,
                        "icon": badge.icon_emoji,
                        "earned": True,
                        "earned_at": row.earned_at.date().isoformat() if row.earned_at else "",
                    }
                )
            else:
                result.append(
                    {
                        "id": badge.id,
                        "name": badge.name,
                        "description": badge.description,
                        "icon": badge.icon_emoji,
                        "earned": False,
                        "progress": self._get_progress(stats, badge),
                    }
                )
        return result

    def _check_condition(self, stats: TeacherStats, badge: BadgeDefinition) -> bool:
        dims = stats.five_dimensions or {}
        condition_map = {
            "lesson_plan_count": stats.total_lesson_plans or 0,
            "micro_analysis_count": stats.total_micro_analysis or 0,
            "visit_record_count": stats.total_visit_records or 0,
            "homework_batch_count": stats.total_homework_batches or 0,
            "forum_post_count": stats.total_forum_posts or 0,
            "five_dimension_avg": (
                sum(dims.values()) / 5 if isinstance(dims, dict) and dims else 0
            ),
        }
        value = condition_map.get(badge.condition_type, 0)
        return value >= badge.condition_threshold

    def _get_progress(self, stats: TeacherStats, badge: BadgeDefinition) -> str:
        mapping = {
            "lesson_plan_count": stats.total_lesson_plans or 0,
            "micro_analysis_count": stats.total_micro_analysis or 0,
            "visit_record_count": stats.total_visit_records or 0,
            "homework_batch_count": stats.total_homework_batches or 0,
            "forum_post_count": stats.total_forum_posts or 0,
            "five_dimension_avg": self._five_dimension_avg(stats),
        }
        current = mapping.get(badge.condition_type, 0)
        if badge.condition_type == "five_dimension_avg":
            return f"{round(current, 1)}/{badge.condition_threshold}"
        return f"{int(current)}/{badge.condition_threshold}"

    @staticmethod
    def _five_dimension_avg(stats: TeacherStats) -> float:
        dims = stats.five_dimensions or {}
        if not isinstance(dims, dict) or not dims:
            return 0
        return sum(dims.values()) / 5
