from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.auth import require_role
from backend.app.db.database import get_db
from backend.app.db.models import LessonPlanRecord, User
from backend.app.services.lesson_plan_generator import LessonPlanGenerator
from backend.app.services.standard_checker import StandardChecker


router = APIRouter(tags=["lesson-plan"])

generator = LessonPlanGenerator()
standard_checker = StandardChecker()


class LessonPlanRequest(BaseModel):
    group_a: str = Field(alias="groupA")
    group_b: str = Field(alias="groupB")
    subject: str
    duration: int
    topic: str

    model_config = {"populate_by_name": True}


class TimeBlockResponse(BaseModel):
    time: str
    group: str
    label: str
    desc: str


class LessonPlanResponse(BaseModel):
    id: str
    title: str
    plan: List[TimeBlockResponse]
    self_study_tasks: Dict[str, str]
    created_at: str


class SaveLessonPlanRequest(BaseModel):
    plan_id: str
    subject: str
    topic: str
    grade_config: str
    duration: int
    plan_json: Dict[str, Any]


class CheckStandardRequest(BaseModel):
    subject: str
    grade: str
    topic: str
    plan_summary: str


@router.post("/api/agent/lesson_plan", response_model=LessonPlanResponse)
async def generate_lesson_plan(
    req: LessonPlanRequest,
    teacher: User = Depends(require_role("teacher")),
) -> LessonPlanResponse:
    plan = await generator.generate(
        group_a=req.group_a,
        group_b=req.group_b,
        subject=req.subject,
        duration=req.duration,
        topic=req.topic,
    )
    return LessonPlanResponse(**plan)


@router.post("/api/lesson_plan/save")
def save_lesson_plan(
    req: SaveLessonPlanRequest,
    teacher: User = Depends(require_role("teacher")),
    db: Session = Depends(get_db),
) -> dict:
    existed = (
        db.query(LessonPlanRecord)
        .filter(LessonPlanRecord.plan_id == req.plan_id)
        .first()
    )
    if existed:
        return {"status": "saved", "record_id": existed.id}

    plan_json = req.plan_json
    self_study_tasks = plan_json.get("self_study_tasks", {})
    record = LessonPlanRecord(
        plan_id=req.plan_id,
        teacher_id=teacher.id,
        subject=req.subject,
        topic=req.topic,
        grade_config=req.grade_config,
        duration=req.duration,
        title=plan_json.get("title", f"{req.subject}《{req.topic}》备课方案"),
        plan_summary=_build_plan_summary(plan_json),
        plan_json=plan_json,
        self_study_tasks=self_study_tasks,
        created_at=datetime.now(timezone.utc),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {"status": "saved", "record_id": record.id}


@router.post("/api/lesson_plan/check_standard")
async def check_standard(
    req: CheckStandardRequest,
    teacher: User = Depends(require_role("teacher")),
) -> dict:
    result = await standard_checker.check(
        subject=req.subject,
        grade=req.grade,
        topic=req.topic,
        plan_text=req.plan_summary,
    )
    return {
        **result,
        "checked_by": teacher.full_name,
    }


def _build_plan_summary(plan_json: Dict[str, Any]) -> str:
    blocks = plan_json.get("plan", [])
    tasks = plan_json.get("self_study_tasks", {})
    lines: List[str] = []
    for block in blocks:
        lines.append(
            f"{block.get('time', '')} {block.get('label', '')} {block.get('desc', '')}"
        )
    if tasks:
        lines.append("A组任务：" + tasks.get("group_a", ""))
        lines.append("B组任务：" + tasks.get("group_b", ""))
    return "\n".join(lines)
