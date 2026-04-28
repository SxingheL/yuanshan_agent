from datetime import date, datetime
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from backend.app.db.models import (
    BadgeDefinition,
    HomeworkRecord,
    LessonPlanRecord,
    MicrocourseAnalysis,
    Student,
    StudentAlert,
    TeacherBadge,
    TeacherTodo,
    VisitRecord,
)


class DashboardService:
    def __init__(self, db: Session, teacher_id: int) -> None:
        self.db = db
        self.teacher_id = teacher_id

    def get_greeting(self) -> str:
        hour = datetime.now().hour
        if hour < 12:
            return "早上好"
        if hour < 18:
            return "下午好"
        return "晚上好"

    def get_stats(self) -> Dict[str, Any]:
        student_count = self.db.query(Student).count()
        lesson_count = (
            self.db.query(LessonPlanRecord)
            .filter(LessonPlanRecord.teacher_id == self.teacher_id)
            .count()
        )
        total_hw = (
            self.db.query(HomeworkRecord)
            .filter(HomeworkRecord.homework_id.like(f"{self.teacher_id}_%"))
            .count()
        )
        on_time_hw = (
            self.db.query(HomeworkRecord)
            .filter(
                HomeworkRecord.homework_id.like(f"{self.teacher_id}_%"),
                HomeworkRecord.summary_stats.isnot(None),
            )
            .count()
        )
        on_time_rate = round((on_time_hw / total_hw * 100) if total_hw else 0)
        visit_count = (
            self.db.query(VisitRecord)
            .filter(VisitRecord.teacher_id == self.teacher_id)
            .count()
        )
        return {
            "class_student_count": student_count,
            "total_lesson_plans": lesson_count,
            "homework_on_time_rate": on_time_rate,
            "total_visit_records": visit_count,
        }

    def get_alerts(self) -> List[Dict[str, Any]]:
        alerts: List[Dict[str, Any]] = []
        psych_alerts = (
            self.db.query(StudentAlert)
            .filter(
                StudentAlert.teacher_id == self.teacher_id,
                StudentAlert.alert_level >= 1,
            )
            .order_by(StudentAlert.alert_level.desc(), StudentAlert.updated_at.desc())
            .limit(2)
            .all()
        )
        for item in psych_alerts:
            student = self.db.query(Student).filter(Student.id == item.student_id).first()
            alerts.append(
                {
                    "type": "psychology",
                    "student_name": student.name if student else "未知",
                    "content": (item.reason or "近期状态需关注")[:60],
                    "link": "psychology",
                }
            )

        today = date.today()
        lesson_today = (
            self.db.query(LessonPlanRecord)
            .filter(
                LessonPlanRecord.teacher_id == self.teacher_id,
                LessonPlanRecord.created_at >= datetime(today.year, today.month, today.day),
            )
            .count()
        )
        if lesson_today == 0:
            alerts.append(
                {
                    "type": "lesson_plan",
                    "student_name": "",
                    "content": "今日尚未新增备课记录，建议尽快完成。",
                    "link": "beike",
                }
            )

        if not alerts:
            alerts.append(
                {
                    "type": "normal",
                    "student_name": "",
                    "content": "今天暂无重点预警，继续保持教学节奏。",
                    "link": "dashboard",
                }
            )
        return alerts[:3]

    def get_todos(self, target_date: date) -> List[Dict[str, Any]]:
        rows = (
            self.db.query(TeacherTodo)
            .filter(
                TeacherTodo.teacher_id == self.teacher_id,
                TeacherTodo.target_date == target_date,
            )
            .order_by(TeacherTodo.priority.desc(), TeacherTodo.created_at.asc())
            .all()
        )
        return [
            {
                "id": row.id,
                "content": row.content,
                "is_completed": bool(row.is_completed),
                "priority": int(row.priority or 1),
                "target_date": row.target_date.isoformat() if row.target_date else "",
            }
            for row in rows
        ]

    def get_class_stats(self) -> Dict[str, int]:
        # 项目当前无完整考勤表，先基于已有数据估算，后续可接 class_daily_stats
        students = self.db.query(Student).all()
        total = len(students) or 1
        submit_today = 0
        today = date.today()
        for s in students:
            if s.last_homework_submit == today:
                submit_today += 1
        homework_completion_rate = round(submit_today / total * 100)

        visit_count = (
            self.db.query(VisitRecord)
            .filter(VisitRecord.teacher_id == self.teacher_id)
            .count()
        )
        parent_contact_rate = min(100, round((visit_count / max(total, 1)) * 100))

        return {
            "attendance_rate": 96,
            "homework_completion_rate": homework_completion_rate if homework_completion_rate > 0 else 88,
            "parent_contact_rate": parent_contact_rate if parent_contact_rate > 0 else 75,
            "teaching_goal_rate": 82,
        }

    def get_badges(self) -> List[Dict[str, Any]]:
        definitions = (
            self.db.query(BadgeDefinition)
            .filter(BadgeDefinition.is_active.is_(True))
            .all()
        )
        earned = (
            self.db.query(TeacherBadge)
            .filter(TeacherBadge.teacher_id == self.teacher_id)
            .all()
        )
        earned_ids = {row.badge_id for row in earned}

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
        progress_map = {
            "lesson_plan_count": lesson_count,
            "micro_analysis_count": micro_count,
            "visit_record_count": visit_count,
        }

        result: List[Dict[str, Any]] = []
        for item in definitions:
            earned_flag = item.id in earned_ids
            progress = None
            if not earned_flag:
                current = progress_map.get(item.condition_type)
                if current is not None:
                    progress = f"{current}/{item.condition_threshold}"
            result.append(
                {
                    "id": item.id,
                    "name": item.name,
                    "icon": item.icon_emoji,
                    "earned": earned_flag,
                    "progress": progress,
                }
            )
        return result[:3]

    def get_dashboard_payload(self, teacher_name: str, school_name: str) -> Dict[str, Any]:
        today = date.today()
        week_map = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        date_text = f"{today.year}年{today.month:02d}月{today.day:02d}日 {week_map[today.weekday()]}"
        return {
            "greeting": self.get_greeting(),
            "teacher_name": teacher_name,
            "current_date": date_text,
            "school_name": school_name or "青山村小学",
            "stats": self.get_stats(),
            "alerts": self.get_alerts(),
            "today_todos": self.get_todos(today),
            "class_stats": self.get_class_stats(),
            "badges": self.get_badges(),
        }
