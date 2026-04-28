from datetime import date, datetime, timezone
from typing import Any, Dict, List

from sqlalchemy import Integer, func
from sqlalchemy.orm import Session

from backend.app.db.models import (
    CareerTemplate,
    KnowledgeMasteryHistory,
    Student,
    StudentAbility,
    StudentDream,
    StudentFlashMoment,
    StudentGoal,
    StudentHomeworkDetail,
    StudentSemesterStats,
)


class StudentArchiveService:
    def __init__(self, db: Session):
        self.db = db

    def get_full_archive(self, student_id: str) -> Dict[str, Any]:
        student = self.db.query(Student).filter(Student.id == student_id).first()
        if not student:
            raise ValueError("学生不存在")

        stats = self.db.query(StudentSemesterStats).filter(StudentSemesterStats.student_id == student_id).first()
        if not stats:
            stats = self.refresh_stats(student_id)

        basic = {
            "name": student.name,
            "school": "青山村小学",
            "grade": student.grade,
            "class_name": self._format_class_name(student.class_id),
            "avg_score": round(float(stats.avg_score or 0), 1),
            "attendance_rate": round(float(stats.attendance_rate or 0), 1),
            "flash_moments_count": int(stats.flash_count or 0),
            "dream": stats.dream or "待定",
        }

        scores = (
            self.db.query(StudentHomeworkDetail.score)
            .filter(StudentHomeworkDetail.student_id == student_id)
            .order_by(StudentHomeworkDetail.created_at.desc())
            .limit(6)
            .all()
        )
        score_trend = [float(item[0]) for item in reversed(scores) if item and item[0] is not None]

        knowledge = self.aggregate_knowledge_mastery(student_id)

        abilities = (
            self.db.query(StudentAbility)
            .filter(StudentAbility.student_id == student_id)
            .order_by(StudentAbility.created_at.desc())
            .all()
        )
        ability_list = [
            {
                "id": row.id,
                "name": row.ability_name,
                "description": row.description or "",
                "source": row.source,
            }
            for row in abilities
        ]

        flashes = (
            self.db.query(StudentFlashMoment)
            .filter(StudentFlashMoment.student_id == student_id, StudentFlashMoment.is_public.is_(True))
            .order_by(StudentFlashMoment.moment_date.desc(), StudentFlashMoment.created_at.desc())
            .limit(10)
            .all()
        )
        flash_list = [
            {
                "id": row.id,
                "date": row.moment_date.isoformat() if row.moment_date else "",
                "polished": row.polished_text or row.original_text,
                "encouragement": row.encouragement or "你真棒，继续加油！",
            }
            for row in flashes
        ]

        goals = (
            self.db.query(StudentGoal)
            .filter(StudentGoal.student_id == student_id)
            .order_by(StudentGoal.is_completed.asc(), StudentGoal.due_date.asc(), StudentGoal.updated_at.desc())
            .all()
        )
        goal_list = [
            {
                "id": row.id,
                "title": row.title,
                "description": row.description,
                "current_progress": int(row.current_progress or 0),
                "target_progress": int(row.target_progress or 100),
                "due_date": row.due_date.isoformat() if row.due_date else "",
                "is_completed": bool(row.is_completed),
                "generated_by": row.generated_by,
            }
            for row in goals
        ]

        return {
            "basic": basic,
            "academic": {
                "score_trend": score_trend,
                "knowledge_mastery": knowledge,
            },
            "abilities": ability_list,
            "flash_moments": flash_list,
            "goals": goal_list,
        }

    def aggregate_knowledge_mastery(self, student_id: str) -> List[Dict[str, Any]]:
        rows = (
            self.db.query(
                KnowledgeMasteryHistory.knowledge_point,
                func.avg(func.cast(KnowledgeMasteryHistory.is_correct, Integer)),
            )
            .filter(KnowledgeMasteryHistory.student_id == student_id)
            .group_by(KnowledgeMasteryHistory.knowledge_point)
            .all()
        )
        result = []
        for point_name, avg_val in rows:
            mastery = round(float(avg_val or 0) * 100)
            result.append(
                {
                    "name": point_name,
                    "mastery": mastery,
                    "trend": "上升" if mastery < 70 else "稳定",
                }
            )
        result.sort(key=lambda x: x["mastery"])
        return result[:8]

    def refresh_stats(self, student_id: str) -> StudentSemesterStats:
        student = self.db.query(Student).filter(Student.id == student_id).first()
        if not student:
            raise ValueError("学生不存在")

        score_rows = (
            self.db.query(StudentHomeworkDetail.score)
            .filter(StudentHomeworkDetail.student_id == student_id)
            .all()
        )
        scores = [float(row[0]) for row in score_rows if row and row[0] is not None]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0

        flash_count = (
            self.db.query(StudentFlashMoment)
            .filter(StudentFlashMoment.student_id == student_id, StudentFlashMoment.is_public.is_(True))
            .count()
        )
        attendance_rate = self._estimate_attendance(student_id)
        dream = self._get_dream(student_id)
        semester = self._calc_semester()

        stats = self.db.query(StudentSemesterStats).filter(StudentSemesterStats.student_id == student_id).first()
        if not stats:
            stats = StudentSemesterStats(student_id=student_id)
            self.db.add(stats)

        stats.semester = semester
        stats.avg_score = avg_score
        stats.attendance_rate = attendance_rate
        stats.flash_count = flash_count
        stats.dream = dream
        stats.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(stats)
        return stats

    def refresh_all_stats(self) -> None:
        students = self.db.query(Student.id).all()
        for row in students:
            self.refresh_stats(row[0])

    def _estimate_attendance(self, student_id: str) -> float:
        student = self.db.query(Student).filter(Student.id == student_id).first()
        if not student:
            return 95.0
        archive = student.growth_archive if isinstance(student.growth_archive, dict) else {}
        rate = archive.get("attendance_rate")
        try:
            return max(60.0, min(100.0, float(rate)))
        except (TypeError, ValueError):
            if student.family_type == "留守":
                return 95.0
            if student.family_type == "困难":
                return 93.0
            return 96.0

    def _get_dream(self, student_id: str) -> str:
        dream = (
            self.db.query(StudentDream)
            .filter(StudentDream.student_id == student_id)
            .order_by(StudentDream.updated_at.desc())
            .first()
        )
        if not dream:
            return "待定"
        if dream.custom_career_name:
            return dream.custom_career_name
        career = self.db.query(CareerTemplate).filter(CareerTemplate.id == dream.career_id).first()
        return career.name if career else "待定"

    def _calc_semester(self) -> str:
        today = date.today()
        year = today.year
        if today.month >= 9:
            return f"{year}-{year + 1}"
        return f"{year - 1}-{year}"

    def _format_class_name(self, class_id: str) -> str:
        if not class_id:
            return "一班"
        if class_id.startswith("class_"):
            return f"{class_id.split('_')[-1]}班"
        return class_id
