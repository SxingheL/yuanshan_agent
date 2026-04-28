from datetime import date, datetime, timedelta, timezone
import json
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.db.models import (
    CareList,
    PsychologyAnalysis,
    Student,
    StudentAlert,
    StudentHomeworkDetail,
    User,
)
from backend.app.services.local_llm import LocalLLM


NEGATIVE_WORDS = [
    "孤单",
    "没意思",
    "不想",
    "烦",
    "难受",
    "害怕",
    "焦虑",
    "抑郁",
    "哭",
    "绝望",
]


class PsychologyAnalyzer:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.llm = LocalLLM()

    def analyze(self, student_id: str, materials: Dict[str, Any], teacher_id: int) -> Dict[str, Any]:
        student = self.db.query(Student).filter(Student.id == student_id).first()
        if not student:
            raise ValueError("学生不存在")

        scores = self._extract_scores(student_id, materials)
        prompt = self._build_prompt(student, materials, scores)
        fallback_result = self._fallback_analysis(student, materials, scores)
        raw = self.llm.generate(prompt, fallback_answer=json.dumps(fallback_result, ensure_ascii=False))
        parsed = self._parse_result(raw)
        result = parsed if parsed else fallback_result
        result = self._normalize_result(result)

        self._save_analysis(student_id, teacher_id, materials, result)
        return result

    def _extract_scores(self, student_id: str, materials: Dict[str, Any]) -> List[float]:
        material_scores = materials.get("score_changes")
        if isinstance(material_scores, list) and material_scores:
            values = []
            for item in material_scores:
                try:
                    values.append(float(item))
                except (TypeError, ValueError):
                    continue
            if values:
                return values[-5:]

        rows = (
            self.db.query(StudentHomeworkDetail.score)
            .filter(StudentHomeworkDetail.student_id == student_id)
            .order_by(StudentHomeworkDetail.created_at.desc())
            .limit(5)
            .all()
        )
        values = [float(row[0]) for row in rows if row and row[0] is not None]
        values.reverse()
        return values

    def _build_prompt(self, student: Student, materials: Dict[str, Any], scores: List[float]) -> str:
        return f"""
你是心理健康初级筛查专家。请根据学生信息与材料做风险分级，并只输出JSON：
{{
  "alert_level": 0-3,
  "reason": "原因（150字以内）",
  "action_suggestion": "可执行建议",
  "today_reminder": "今日可做的小行动"
}}
评分规则提示：
- 成绩连续下滑、明显消极词汇、留守/单亲/困难等叠加时提高等级
- 0=正常 1=观察 2=谈心 3=紧急（需马上联动家长/心理支持）
学生信息：姓名={student.name}，年级={student.grade}，家庭类型={student.family_type or '未标注'}
近期成绩：{scores}
材料：{json.dumps(materials, ensure_ascii=False)}
""".strip()

    def _fallback_analysis(self, student: Student, materials: Dict[str, Any], scores: List[float]) -> Dict[str, Any]:
        text = " ".join(
            str(materials.get(key, "") or "")
            for key in ["essay_text", "teacher_notes", "visit_diary", "conversation_record"]
        )
        has_negative_words = any(word in text for word in NEGATIVE_WORDS)
        score_down = len(scores) >= 3 and scores[-1] < scores[-2] <= scores[-3]
        risk_family = student.family_type in {"留守", "单亲", "困难"}

        level = 0
        reasons = []
        if score_down:
            level = max(level, 2)
            reasons.append("成绩连续下滑")
        elif len(scores) >= 2 and scores[-1] < scores[-2]:
            level = max(level, 1)
            reasons.append("近期成绩有波动")
        if has_negative_words:
            level = max(level, 2)
            reasons.append("文本中出现消极表达")
        if risk_family:
            level = max(level, 1)
            reasons.append(f"家庭类型为{student.family_type}")
        if "绝望" in text or "不想活" in text:
            level = 3
            reasons.append("出现高危表达")
        if not reasons:
            reasons.append("当前未发现明显风险信号")

        suggestion_map = {
            0: "保持日常关注，每周一次积极反馈，持续观察状态。",
            1: "本周安排一次轻量谈话，关注情绪变化，并与家长保持简短沟通。",
            2: "本周进行1次单独谈心并联系监护人，制定两周跟进计划。",
            3: "立即联系监护人并启动校内心理支持流程，安排当天重点陪伴。",
        }
        reminder_map = {
            0: f"今天表扬{student.name}一次具体进步，增强安全感。",
            1: f"今天课后与{student.name}聊3分钟，先从兴趣话题开始。",
            2: f"今天优先和{student.name}单独沟通，确认其近期情绪触发点。",
            3: f"今天第一时间联系家长并确保{student.name}处于可支持环境。",
        }
        return {
            "alert_level": level,
            "reason": "，".join(reasons)[:150],
            "action_suggestion": suggestion_map[level],
            "today_reminder": reminder_map[level],
        }

    def _parse_result(self, raw: str) -> Dict[str, Any]:
        if not raw:
            return {}
        text = raw.strip()
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                data = json.loads(text[start : end + 1])
                if isinstance(data, dict):
                    return data
            except Exception:
                return {}
        return {}

    def _normalize_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        alert_level = result.get("alert_level", 0)
        try:
            level = int(alert_level)
        except (TypeError, ValueError):
            level = 0
        level = max(0, min(3, level))
        return {
            "alert_level": level,
            "reason": str(result.get("reason", "") or "")[:150],
            "action_suggestion": str(result.get("action_suggestion", "") or "")[:300],
            "today_reminder": str(result.get("today_reminder", "") or "")[:160],
        }

    def _save_analysis(self, student_id: str, teacher_id: int, materials: Dict[str, Any], result: Dict[str, Any]) -> None:
        today = date.today()
        analysis = PsychologyAnalysis(
            student_id=student_id,
            teacher_id=teacher_id,
            analysis_date=today,
            materials=materials,
            alert_level=result["alert_level"],
            alert_reason=result["reason"],
            action_suggestion=result["action_suggestion"],
            today_reminder=result["today_reminder"],
        )
        self.db.add(analysis)

        alert = (
            self.db.query(StudentAlert)
            .filter(
                StudentAlert.teacher_id == teacher_id,
                StudentAlert.student_id == student_id,
            )
            .first()
        )
        if not alert:
            alert = StudentAlert(teacher_id=teacher_id, student_id=student_id)
            self.db.add(alert)
        alert.alert_level = result["alert_level"]
        alert.reason = result["reason"]
        alert.suggestion = result["action_suggestion"]
        alert.today_reminder = result["today_reminder"]
        alert.last_analysis_date = today
        alert.updated_at = datetime.now(timezone.utc)

        self.db.commit()


class CareListService:
    def __init__(self, db: Session, teacher_id: int) -> None:
        self.db = db
        self.teacher_id = teacher_id

    def generate_weekly_list(self, force_refresh: bool = False) -> None:
        if force_refresh:
            (
                self.db.query(CareList)
                .filter(
                    CareList.teacher_id == self.teacher_id,
                    CareList.list_type == "week",
                    CareList.source == "ai",
                    CareList.is_completed.is_(False),
                )
                .delete(synchronize_session=False)
            )
            self.db.commit()

        existing = {
            f"{row.student_id}:{row.content}"
            for row in self.db.query(CareList)
            .filter(
                CareList.teacher_id == self.teacher_id,
                CareList.list_type == "week",
                CareList.is_completed.is_(False),
            )
            .all()
        }
        alerts = (
            self.db.query(StudentAlert)
            .filter(
                StudentAlert.teacher_id == self.teacher_id,
                StudentAlert.alert_level >= 1,
            )
            .order_by(StudentAlert.alert_level.desc(), StudentAlert.updated_at.desc())
            .all()
        )
        due_date = date.today() + timedelta(days=6)
        changed = False
        for alert in alerts:
            content = (alert.suggestion or "").strip()
            if not content:
                continue
            key = f"{alert.student_id}:{content}"
            if key in existing:
                continue
            self.db.add(
                CareList(
                    teacher_id=self.teacher_id,
                    student_id=alert.student_id,
                    list_type="week",
                    content=content,
                    priority=max(1, int(alert.alert_level or 1)),
                    is_completed=False,
                    due_date=due_date,
                    source="ai",
                )
            )
            changed = True
        if changed:
            self.db.commit()

    def refresh_today_reminder(self) -> None:
        today = date.today()
        (
            self.db.query(CareList)
            .filter(
                CareList.teacher_id == self.teacher_id,
                CareList.list_type == "today",
                CareList.source == "ai",
                CareList.is_completed.is_(False),
            )
            .delete(synchronize_session=False)
        )
        alert = (
            self.db.query(StudentAlert)
            .filter(StudentAlert.teacher_id == self.teacher_id)
            .order_by(StudentAlert.alert_level.desc(), StudentAlert.updated_at.desc())
            .first()
        )
        if alert:
            content = (
                alert.today_reminder
                or f"今日关怀：优先关注学生 {alert.student_id}，{(alert.suggestion or '')[:100]}"
            )
            self.db.add(
                CareList(
                    teacher_id=self.teacher_id,
                    student_id=alert.student_id,
                    list_type="today",
                    content=content[:160],
                    priority=max(1, int(alert.alert_level or 1)),
                    is_completed=False,
                    due_date=today,
                    source="ai",
                )
            )
        self.db.commit()

    def get_today_reminder(self) -> Dict[str, str]:
        today = date.today()
        reminder = (
            self.db.query(CareList)
            .filter(
                CareList.teacher_id == self.teacher_id,
                CareList.list_type == "today",
                CareList.is_completed.is_(False),
                CareList.due_date == today,
            )
            .order_by(CareList.priority.desc(), CareList.created_at.asc())
            .first()
        )
        if reminder:
            return {"reminder": reminder.content, "item_id": reminder.id}

        top = (
            self.db.query(StudentAlert)
            .filter(StudentAlert.teacher_id == self.teacher_id)
            .order_by(StudentAlert.alert_level.desc(), StudentAlert.updated_at.desc())
            .first()
        )
        if top:
            fallback = top.today_reminder or f"今日关怀：{(top.suggestion or '')[:100]}"
            return {"reminder": fallback}
        return {"reminder": "无特别提醒"}

    def get_alerts(self) -> List[Dict[str, Any]]:
        rows = (
            self.db.query(StudentAlert, Student)
            .join(Student, Student.id == StudentAlert.student_id)
            .filter(StudentAlert.teacher_id == self.teacher_id)
            .order_by(StudentAlert.alert_level.desc(), StudentAlert.updated_at.desc())
            .all()
        )
        return [
            {
                "student_id": student.id,
                "student_name": student.name,
                "grade": student.grade,
                "alert_level": int(alert.alert_level or 0),
                "reason": alert.reason or "",
                "suggestion": alert.suggestion or "",
                "today_reminder": alert.today_reminder or "",
                "last_analysis_date": alert.last_analysis_date.isoformat()
                if alert.last_analysis_date
                else "",
            }
            for alert, student in rows
        ]

    def get_weekly_list(self) -> List[Dict[str, Any]]:
        self.generate_weekly_list(force_refresh=False)
        rows = (
            self.db.query(CareList, Student)
            .outerjoin(Student, Student.id == CareList.student_id)
            .filter(
                CareList.teacher_id == self.teacher_id,
                CareList.list_type == "week",
            )
            .order_by(CareList.is_completed.asc(), CareList.priority.desc(), CareList.created_at.asc())
            .all()
        )
        items = []
        for row, student in rows:
            items.append(
                {
                    "id": row.id,
                    "student_id": row.student_id,
                    "student_name": student.name if student else "",
                    "content": row.content,
                    "priority": row.priority,
                    "is_completed": bool(row.is_completed),
                    "due_date": row.due_date.isoformat() if row.due_date else "",
                    "source": row.source,
                }
            )
        return items

    def add_weekly_item(
        self,
        content: str,
        student_id: Optional[str] = None,
        priority: int = 1,
        due_date: Optional[date] = None,
        source: str = "manual",
    ) -> Dict[str, Any]:
        item = CareList(
            teacher_id=self.teacher_id,
            student_id=student_id,
            list_type="week",
            content=content.strip(),
            priority=max(1, min(3, int(priority))),
            is_completed=False,
            due_date=due_date,
            source=source,
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return {
            "id": item.id,
            "content": item.content,
            "priority": item.priority,
            "is_completed": item.is_completed,
            "source": item.source,
        }

    def update_weekly_item(
        self,
        item_id: int,
        content: Optional[str] = None,
        priority: Optional[int] = None,
        is_completed: Optional[bool] = None,
    ) -> Dict[str, Any]:
        row = (
            self.db.query(CareList)
            .filter(
                CareList.id == item_id,
                CareList.teacher_id == self.teacher_id,
                CareList.list_type == "week",
            )
            .first()
        )
        if not row:
            raise ValueError("清单项不存在")
        if content is not None:
            row.content = content.strip()
        if priority is not None:
            row.priority = max(1, min(3, int(priority)))
        if is_completed is not None:
            row.is_completed = bool(is_completed)
        self.db.commit()
        return {"id": row.id, "message": "更新成功"}

    def delete_weekly_item(self, item_id: int) -> None:
        row = (
            self.db.query(CareList)
            .filter(
                CareList.id == item_id,
                CareList.teacher_id == self.teacher_id,
                CareList.list_type == "week",
            )
            .first()
        )
        if not row:
            raise ValueError("清单项不存在")
        self.db.delete(row)
        self.db.commit()


def refresh_daily_reminder_for_all(db: Session) -> None:
    teachers = db.query(User).filter(User.role == "teacher").all()
    for teacher in teachers:
        CareListService(db, teacher.id).refresh_today_reminder()


def refresh_weekly_list_for_all(db: Session) -> None:
    teachers = db.query(User).filter(User.role == "teacher").all()
    for teacher in teachers:
        CareListService(db, teacher.id).generate_weekly_list(force_refresh=True)
