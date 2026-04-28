from datetime import date, datetime
import json
from typing import Any, Dict, List

from sqlalchemy import Integer, func
from sqlalchemy.orm import Session

from backend.app.db.models import (
    CareerTemplate,
    KnowledgeMasteryHistory,
    Student,
    StudentDream,
    StudentGoal,
    StudentHomeworkDetail,
)
from backend.app.services.local_llm import LocalLLM


class GoalGenerator:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.llm = LocalLLM()

    def generate_goals(self, student_id: str, generated_by: str = "ai") -> List[Dict[str, Any]]:
        student = self.db.query(Student).filter(Student.id == student_id).first()
        if not student:
            raise ValueError("学生不存在")

        weak_kps = (
            self.db.query(
                KnowledgeMasteryHistory.knowledge_point,
                func.avg(func.cast(KnowledgeMasteryHistory.is_correct, Integer)),
            )
            .filter(KnowledgeMasteryHistory.student_id == student_id)
            .group_by(KnowledgeMasteryHistory.knowledge_point)
            .having(func.avg(func.cast(KnowledgeMasteryHistory.is_correct, Integer)) < 0.7)
            .all()
        )
        weak_list = [row[0] for row in weak_kps]
        score_trend = self._get_score_trend(student_id)
        recent_avg = round(sum(score_trend[-3:]) / max(1, min(3, len(score_trend))), 1) if score_trend else 80
        dream = self._get_dream_name(student_id) or "待定"

        prompt = f"""
为山区小学生制定3~5条阶段性目标，输出JSON数组：
[
  {{"title":"...","description":"...","due_date":"YYYY-MM-DD","target_progress":100}}
]
学生信息：
- 姓名：{student.name}
- 年级：{student.grade}
- 梦想：{dream}
- 近期成绩趋势：{score_trend}
- 近期平均分：{recent_avg}
- 薄弱知识点：{ "、".join(weak_list) if weak_list else "暂无明显薄弱点" }
要求：
1. 目标可执行、可量化、符合年龄特点。
2. 禁止不现实承诺，强调持续努力。
3. 描述简洁，鼓励性表达。
""".strip()

        fallback = self._fallback_goals(student.grade, dream, weak_list)
        raw = self.llm.generate(prompt, fallback_answer=json.dumps(fallback, ensure_ascii=False))
        goals_data = self._parse_goals(raw) or fallback

        saved_rows: List[StudentGoal] = []
        for item in goals_data[:5]:
            title = str(item.get("title", "") or "").strip()[:120]
            desc = str(item.get("description", "") or "").strip()[:220]
            due = self._parse_due_date(str(item.get("due_date", "") or ""))
            target = item.get("target_progress", 100)
            try:
                target_progress = max(1, min(100, int(target)))
            except (TypeError, ValueError):
                target_progress = 100
            if not title:
                continue
            row = StudentGoal(
                student_id=student_id,
                title=title,
                description=desc or "按计划持续推进目标。",
                target_progress=target_progress,
                current_progress=0,
                due_date=due,
                is_completed=False,
                generated_by=generated_by,
            )
            self.db.add(row)
            saved_rows.append(row)
        self.db.commit()
        for row in saved_rows:
            self.db.refresh(row)
        return [
            {
                "id": row.id,
                "title": row.title,
                "description": row.description,
                "current_progress": row.current_progress,
                "target_progress": row.target_progress,
                "due_date": row.due_date.isoformat() if row.due_date else "",
            }
            for row in saved_rows
        ]

    def _get_score_trend(self, student_id: str) -> List[float]:
        rows = (
            self.db.query(StudentHomeworkDetail.score)
            .filter(StudentHomeworkDetail.student_id == student_id)
            .order_by(StudentHomeworkDetail.created_at.desc())
            .limit(6)
            .all()
        )
        values = [float(r[0]) for r in rows if r and r[0] is not None]
        values.reverse()
        return values

    def _get_dream_name(self, student_id: str) -> str:
        dream = (
            self.db.query(StudentDream)
            .filter(StudentDream.student_id == student_id)
            .order_by(StudentDream.updated_at.desc())
            .first()
        )
        if not dream:
            return ""
        if dream.custom_career_name:
            return dream.custom_career_name
        career = self.db.query(CareerTemplate).filter(CareerTemplate.id == dream.career_id).first()
        return career.name if career else ""

    def _parse_goals(self, raw: str) -> List[Dict[str, Any]]:
        if not raw:
            return []
        text = raw.strip()
        try:
            data = json.loads(text)
            return data if isinstance(data, list) else []
        except Exception:
            pass
        start = text.find("[")
        end = text.rfind("]")
        if start >= 0 and end > start:
            try:
                data = json.loads(text[start : end + 1])
                return data if isinstance(data, list) else []
            except Exception:
                return []
        return []

    def _parse_due_date(self, text: str) -> date:
        txt = text.strip()
        for fmt in ("%Y-%m-%d", "%Y-%m"):
            try:
                dt = datetime.strptime(txt, fmt)
                if fmt == "%Y-%m":
                    return date(dt.year, dt.month, 28)
                return dt.date()
            except Exception:
                continue
        today = date.today()
        return date(today.year, min(12, today.month + 2), 28)

    def _fallback_goals(self, grade: str, dream: str, weak_list: List[str]) -> List[Dict[str, Any]]:
        weak = weak_list[0] if weak_list else "计算基础"
        return [
            {
                "title": f"学业提升：攻克{weak}",
                "description": f"{grade}本学期将{weak}相关练习正确率提升到80%以上，每周完成2次针对训练。",
                "due_date": date.today().replace(day=28).isoformat(),
                "target_progress": 100,
            },
            {
                "title": "学习习惯：每日复盘15分钟",
                "description": "每天作业后复盘1个错题或1个知识点，连续坚持4周。",
                "due_date": date.today().replace(day=28).isoformat(),
                "target_progress": 100,
            },
            {
                "title": f"梦想连接：走近“{dream}”",
                "description": "每周阅读1篇与梦想职业相关的科普材料，并向老师分享1个收获。",
                "due_date": date.today().replace(day=28).isoformat(),
                "target_progress": 100,
            },
        ]
