from statistics import mean
from typing import Dict, List

from sqlalchemy.orm import Session

from backend.app.db.models import (
    KnowledgeMasteryHistory,
    Student,
    StudentHomeworkDetail,
)
from backend.app.services.local_llm import LocalLLM


class VisitSuggestionService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.llm = LocalLLM()

    def generate_for_student(self, student_id: str) -> Dict:
        student = self.db.query(Student).filter(Student.id == student_id).first()
        if not student:
            return {"error": "学生不存在"}

        scores = (
            self.db.query(StudentHomeworkDetail.score)
            .filter(StudentHomeworkDetail.student_id == student_id)
            .order_by(StudentHomeworkDetail.created_at.desc())
            .limit(5)
            .all()
        )
        score_list = [float(row[0]) for row in scores if row and row[0] is not None]
        trend = self._score_trend(score_list)

        wrong_points = (
            self.db.query(KnowledgeMasteryHistory.knowledge_point)
            .filter(
                KnowledgeMasteryHistory.student_id == student_id,
                KnowledgeMasteryHistory.is_correct.is_(False),
            )
            .order_by(KnowledgeMasteryHistory.homework_date.desc())
            .limit(10)
            .all()
        )
        unique_wrong = []
        for row in wrong_points:
            kp = row[0]
            if kp and kp not in unique_wrong:
                unique_wrong.append(kp)
            if len(unique_wrong) >= 3:
                break

        growth = student.growth_archive or {}
        psych_signals = growth.get("psychology_signals", [])
        if isinstance(psych_signals, str):
            psych_signals = [psych_signals]

        prompt = f"""
学生：{student.name}
家庭类型：{student.family_type or '未标注'}
成绩趋势：{trend}，最近分数：{score_list or '暂无'}
常错知识点：{unique_wrong or '暂无'}
心理信号：{psych_signals or '暂无'}
请给出家访建议，输出JSON：
{{
  "suggested_topics":["..."],
  "suggested_questions":["..."],
  "action_items":["..."]
}}
""".strip()

        fallback = self._fallback_suggestion(student.name, student.family_type, trend, unique_wrong, psych_signals)
        raw = self.llm.generate(prompt, fallback_answer="")
        parsed = self._try_parse(raw)
        result = parsed if parsed else fallback
        result["student_name"] = student.name
        return result

    def suggest_targets(self, class_id: str = "", limit: int = 5) -> Dict:
        query = self.db.query(Student)
        if class_id:
            query = query.filter(Student.class_id == class_id)
        students = query.all()
        rows = []
        for stu in students:
            score_rows = (
                self.db.query(StudentHomeworkDetail.score)
                .filter(StudentHomeworkDetail.student_id == stu.id)
                .order_by(StudentHomeworkDetail.created_at.desc())
                .limit(3)
                .all()
            )
            scores = [float(row[0]) for row in score_rows if row and row[0] is not None]
            trend_weight = 0
            if len(scores) >= 2 and scores[0] < scores[-1]:
                trend_weight += 2
            if scores and mean(scores) < 70:
                trend_weight += 2

            wrong_count = (
                self.db.query(KnowledgeMasteryHistory)
                .filter(
                    KnowledgeMasteryHistory.student_id == stu.id,
                    KnowledgeMasteryHistory.is_correct.is_(False),
                )
                .count()
            )
            family_weight = 1 if stu.family_type in {"留守", "单亲", "困难"} else 0
            score = trend_weight + min(3, wrong_count // 2) + family_weight
            rows.append(
                {
                    "student_id": stu.id,
                    "student_name": stu.name,
                    "class_id": stu.class_id,
                    "family_type": stu.family_type,
                    "priority_score": score,
                    "reason": self._target_reason(stu.family_type, scores, wrong_count),
                }
            )

        rows.sort(key=lambda item: item["priority_score"], reverse=True)
        return {"items": rows[:limit]}

    def _target_reason(self, family_type: str, scores: List[float], wrong_count: int) -> str:
        reasons = []
        if family_type in {"留守", "单亲", "困难"}:
            reasons.append(f"家庭类型为{family_type}")
        if len(scores) >= 2 and scores[0] < scores[-1]:
            reasons.append("近期成绩有下滑")
        if wrong_count >= 3:
            reasons.append("错题累计较多")
        return "；".join(reasons) if reasons else "建议常规沟通，了解学习与家庭情况"

    def _score_trend(self, scores: List[float]) -> str:
        if len(scores) < 2:
            return "数据不足"
        if scores[0] < scores[-1]:
            return "下降"
        if scores[0] > scores[-1]:
            return "上升"
        return "平稳"

    def _fallback_suggestion(
        self,
        student_name: str,
        family_type: str,
        trend: str,
        wrong_points: List[str],
        psych_signals: List[str],
    ) -> Dict:
        topics = []
        if trend == "下降":
            topics.append("成绩波动：近期分数有下滑，建议一起看学习时间与作业习惯")
        if wrong_points:
            topics.append(f"学业重点：最近常错知识点为{','.join(wrong_points)}，建议家校协同巩固")
        if psych_signals:
            topics.append(f"心理信号：最近记录到{psych_signals[0]}，建议温和了解孩子情绪变化")
        if family_type:
            topics.append(f"家庭情况：{family_type}，建议沟通日常陪伴和学习支持方式")
        if not topics:
            topics.append("常规沟通：了解孩子学习状态、作息和同伴相处情况")

        return {
            "student_name": student_name,
            "suggested_topics": topics[:3],
            "suggested_questions": [
                "最近在家里谁会陪孩子做作业？",
                "孩子最近有没有特别开心或烦恼的事情？",
                "家庭在学习支持上最需要学校帮助的是什么？",
            ],
            "action_items": [
                "带一张鼓励卡片，先肯定孩子近期努力",
                "记录一项可执行的家校共同行动，并约定下次回访时间",
            ],
        }

    def _try_parse(self, raw: str) -> Dict:
        import json
        import re

        if not raw:
            return {}
        text = raw.strip()
        try:
            data = json.loads(text)
            if {"suggested_topics", "suggested_questions", "action_items"} <= set(data.keys()):
                return data
        except Exception:
            pass
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            return {}
        try:
            data = json.loads(m.group(0))
            if {"suggested_topics", "suggested_questions", "action_items"} <= set(data.keys()):
                return data
        except Exception:
            return {}
        return {}
