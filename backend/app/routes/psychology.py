from datetime import date
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.auth import require_role
from backend.app.db.database import get_db
from backend.app.db.models import Student, User
from backend.app.services.psychology_service import CareListService, PsychologyAnalyzer


router = APIRouter(prefix="/api/psychology", tags=["psychology"])


class AnalyzeRequest(BaseModel):
    student_id: str
    materials: Dict[str, Any]


class WeeklyCreateRequest(BaseModel):
    student_id: Optional[str] = None
    content: str = Field(..., min_length=1, max_length=300)
    priority: int = Field(default=1, ge=1, le=3)
    due_date: Optional[date] = None


class WeeklyUpdateRequest(BaseModel):
    content: Optional[str] = Field(default=None, min_length=1, max_length=300)
    priority: Optional[int] = Field(default=None, ge=1, le=3)
    is_completed: Optional[bool] = None


@router.post("/analyze")
def analyze(
    req: AnalyzeRequest,
    teacher: User = Depends(require_role("teacher")),
    db: Session = Depends(get_db),
) -> dict:
    analyzer = PsychologyAnalyzer(db)
    try:
        result = analyzer.analyze(req.student_id, req.materials, teacher.id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    care_service = CareListService(db, teacher.id)
    care_service.refresh_today_reminder()
    care_service.generate_weekly_list(force_refresh=False)
    return result


@router.get("/alerts")
def get_alerts(
    teacher: User = Depends(require_role("teacher")),
    db: Session = Depends(get_db),
) -> dict:
    service = CareListService(db, teacher.id)
    return {"items": service.get_alerts()}


@router.get("/today_reminder")
def today_reminder(
    teacher: User = Depends(require_role("teacher")),
    db: Session = Depends(get_db),
) -> dict:
    service = CareListService(db, teacher.id)
    service.refresh_today_reminder()
    return service.get_today_reminder()


@router.get("/weekly_list")
def weekly_list(
    teacher: User = Depends(require_role("teacher")),
    db: Session = Depends(get_db),
) -> dict:
    service = CareListService(db, teacher.id)
    return {"items": service.get_weekly_list()}


@router.post("/weekly_list")
def create_weekly_item(
    req: WeeklyCreateRequest,
    teacher: User = Depends(require_role("teacher")),
    db: Session = Depends(get_db),
) -> dict:
    service = CareListService(db, teacher.id)
    if req.student_id:
        student = db.query(Student).filter(Student.id == req.student_id).first()
        if not student:
            raise HTTPException(status_code=404, detail="学生不存在")
    item = service.add_weekly_item(
        content=req.content,
        student_id=req.student_id,
        priority=req.priority,
        due_date=req.due_date,
        source="manual",
    )
    return {"item": item}


@router.put("/weekly_list/{item_id}")
def update_weekly_item(
    item_id: int,
    req: WeeklyUpdateRequest,
    teacher: User = Depends(require_role("teacher")),
    db: Session = Depends(get_db),
) -> dict:
    service = CareListService(db, teacher.id)
    try:
        return service.update_weekly_item(
            item_id=item_id,
            content=req.content,
            priority=req.priority,
            is_completed=req.is_completed,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/weekly_list/{item_id}")
def delete_weekly_item(
    item_id: int,
    teacher: User = Depends(require_role("teacher")),
    db: Session = Depends(get_db),
) -> dict:
    service = CareListService(db, teacher.id)
    try:
        service.delete_weekly_item(item_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"message": "删除成功"}


@router.get("/students")
def list_students(
    class_id: Optional[str] = None,
    teacher: User = Depends(require_role("teacher")),
    db: Session = Depends(get_db),
) -> dict:
    query = db.query(Student)
    if class_id:
        query = query.filter(Student.class_id == class_id)
    rows = query.order_by(Student.class_id.asc(), Student.name.asc()).all()
    return {
        "items": [
            {
                "id": s.id,
                "name": s.name,
                "class_id": s.class_id,
                "grade": s.grade,
                "family_type": s.family_type,
            }
            for s in rows
        ]
    }
