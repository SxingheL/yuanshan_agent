from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.auth import require_role
from backend.app.db.database import get_db
from backend.app.db.models import Student, StudentAbility, StudentFlashMoment, User
from backend.app.services.flash_polisher import FlashPolisher
from backend.app.services.goal_generator import GoalGenerator
from backend.app.services.student_archive import StudentArchiveService


router = APIRouter(tags=["student_archive"])


class FlashMomentRequest(BaseModel):
    student_id: str
    original_text: str = Field(..., min_length=2, max_length=300)
    moment_date: Optional[date] = None
    is_public: bool = True


class AbilityRequest(BaseModel):
    student_id: str
    ability_name: str = Field(..., min_length=1, max_length=64)
    description: str = Field(default="", max_length=220)


class GoalGenerateRequest(BaseModel):
    student_id: str


def _resolve_student_by_user(db: Session, user: User) -> Optional[Student]:
    return db.query(Student).filter(Student.name == user.full_name).first()


def _assert_archive_permission(db: Session, current_user: User, student_id: str) -> None:
    if current_user.role == "teacher":
        return
    if current_user.role == "student":
        student = _resolve_student_by_user(db, current_user)
        if student and student.id == student_id:
            return
    raise HTTPException(status_code=403, detail="无权访问该学生档案")


@router.get("/api/student/archive/{student_id}")
def get_archive(
    student_id: str,
    current_user: User = Depends(require_role("student", "teacher")),
    db: Session = Depends(get_db),
) -> dict:
    _assert_archive_permission(db, current_user, student_id)
    service = StudentArchiveService(db)
    try:
        return service.get_full_archive(student_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/api/teacher/flash_moment")
def add_flash_moment(
    req: FlashMomentRequest,
    teacher: User = Depends(require_role("teacher")),
    db: Session = Depends(get_db),
) -> dict:
    student = db.query(Student).filter(Student.id == req.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")

    polisher = FlashPolisher()
    polished = polisher.polish(req.original_text)
    row = StudentFlashMoment(
        student_id=req.student_id,
        teacher_id=teacher.id,
        original_text=req.original_text.strip(),
        polished_text=polished["polished"],
        encouragement=polished["encouragement"],
        moment_date=req.moment_date or date.today(),
        is_public=req.is_public,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    StudentArchiveService(db).refresh_stats(req.student_id)

    return {
        "id": row.id,
        "polished_text": row.polished_text,
        "encouragement": row.encouragement,
        "date": row.moment_date.isoformat() if row.moment_date else "",
    }


@router.post("/api/student/ability")
def add_ability(
    req: AbilityRequest,
    current_user: User = Depends(require_role("student", "teacher")),
    db: Session = Depends(get_db),
) -> dict:
    _assert_archive_permission(db, current_user, req.student_id)
    row = StudentAbility(
        student_id=req.student_id,
        ability_name=req.ability_name.strip(),
        description=req.description.strip(),
        source="teacher" if current_user.role == "teacher" else "student",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "id": row.id,
        "name": row.ability_name,
        "description": row.description,
        "source": row.source,
    }


@router.delete("/api/student/ability/{ability_id}")
def delete_ability(
    ability_id: int,
    current_user: User = Depends(require_role("student", "teacher")),
    db: Session = Depends(get_db),
) -> dict:
    row = db.query(StudentAbility).filter(StudentAbility.id == ability_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="能力标签不存在")
    _assert_archive_permission(db, current_user, row.student_id)
    db.delete(row)
    db.commit()
    return {"message": "删除成功"}


@router.post("/api/student/generate_goals")
def generate_goals(
    req: GoalGenerateRequest,
    current_user: User = Depends(require_role("student", "teacher")),
    db: Session = Depends(get_db),
) -> dict:
    _assert_archive_permission(db, current_user, req.student_id)
    try:
        goals = GoalGenerator(db).generate_goals(req.student_id, generated_by="ai")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    StudentArchiveService(db).refresh_stats(req.student_id)
    return {"goals": goals}
