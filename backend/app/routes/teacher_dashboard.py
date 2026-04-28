from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.auth import require_role
from backend.app.db.database import get_db
from backend.app.db.models import TeacherTodo, User
from backend.app.services.dashboard_service import DashboardService


router = APIRouter(prefix="/api/teacher", tags=["teacher-dashboard"])


class TodoCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=200)
    priority: int = Field(default=1, ge=1, le=2)
    target_date: Optional[date] = None


class TodoUpdate(BaseModel):
    content: Optional[str] = Field(default=None, min_length=1, max_length=200)
    completed: Optional[bool] = None
    priority: Optional[int] = Field(default=None, ge=1, le=2)


@router.get("/dashboard")
def get_dashboard(
    teacher: User = Depends(require_role("teacher")),
    db: Session = Depends(get_db),
) -> dict:
    service = DashboardService(db, teacher.id)
    return service.get_dashboard_payload(
        teacher_name=teacher.full_name.replace("老师", ""),
        school_name=teacher.school_name,
    )


@router.get("/todos")
def get_todos(
    target_date: Optional[date] = None,
    teacher: User = Depends(require_role("teacher")),
    db: Session = Depends(get_db),
) -> dict:
    selected = target_date or date.today()
    service = DashboardService(db, teacher.id)
    return {"items": service.get_todos(selected), "target_date": selected.isoformat()}


@router.post("/todos")
def create_todo(
    req: TodoCreate,
    teacher: User = Depends(require_role("teacher")),
    db: Session = Depends(get_db),
) -> dict:
    row = TeacherTodo(
        teacher_id=teacher.id,
        content=req.content.strip(),
        priority=req.priority,
        target_date=req.target_date or date.today(),
        is_completed=False,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id}


@router.put("/todos/{todo_id}")
def update_todo(
    todo_id: int,
    req: TodoUpdate,
    teacher: User = Depends(require_role("teacher")),
    db: Session = Depends(get_db),
) -> dict:
    row = (
        db.query(TeacherTodo)
        .filter(TeacherTodo.id == todo_id, TeacherTodo.teacher_id == teacher.id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="待办事项不存在")
    if req.content is not None:
        row.content = req.content.strip()
    if req.completed is not None:
        row.is_completed = bool(req.completed)
    if req.priority is not None:
        row.priority = req.priority
    db.commit()
    return {"message": "更新成功"}


@router.delete("/todos/{todo_id}")
def delete_todo(
    todo_id: int,
    teacher: User = Depends(require_role("teacher")),
    db: Session = Depends(get_db),
) -> dict:
    row = (
        db.query(TeacherTodo)
        .filter(TeacherTodo.id == todo_id, TeacherTodo.teacher_id == teacher.id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="待办事项不存在")
    db.delete(row)
    db.commit()
    return {"message": "删除成功"}
