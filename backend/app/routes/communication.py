from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.auth import require_role
from backend.app.db.database import get_db
from backend.app.db.models import NoticeRecord, Student, User, VisitRecord
from backend.app.services.notice_generator import NoticeGenerator
from backend.app.services.visit_suggestion import VisitSuggestionService


router = APIRouter(tags=["communication"])


class NoticeRequest(BaseModel):
    draft: str
    is_voice: bool = False


class VisitRecordUpsertRequest(BaseModel):
    student_id: str = Field(..., min_length=1)
    visit_date: date
    content: str = ""
    notes: str = ""


@router.post("/api/communication/generate_notice")
def generate_notice(
    request: NoticeRequest,
    teacher: User = Depends(require_role("teacher")),
    db: Session = Depends(get_db),
) -> dict:
    generator = NoticeGenerator()
    result = generator.generate(request.draft)
    db.add(
        NoticeRecord(
            teacher_id=teacher.id,
            draft=request.draft.strip(),
            short_version=result.get("short_notice", ""),
            rich_version=result.get("rich_notice", ""),
        )
    )
    db.commit()
    result["generated_by"] = teacher.full_name
    return result


@router.get("/api/communication/students")
def list_students_for_visit(
    class_id: Optional[str] = Query(default=None),
    teacher: User = Depends(require_role("teacher")),
    db: Session = Depends(get_db),
) -> dict:
    query = db.query(Student)
    if class_id:
        query = query.filter(Student.class_id == class_id)
    students = query.order_by(Student.class_id.asc(), Student.name.asc()).all()
    return {
        "items": [
            {
                "id": s.id,
                "name": s.name,
                "class_id": s.class_id,
                "grade": s.grade,
                "family_type": s.family_type,
            }
            for s in students
        ]
    }


@router.post("/api/visit_records")
@router.post("/api/communication/visit_records")
def create_visit_record(
    request: VisitRecordUpsertRequest,
    teacher: User = Depends(require_role("teacher")),
    db: Session = Depends(get_db),
) -> dict:
    student = db.query(Student).filter(Student.id == request.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")

    record = VisitRecord(
        teacher_id=teacher.id,
        student_id=request.student_id,
        visit_date=request.visit_date,
        content=request.content.strip(),
        notes=request.notes.strip(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {"id": record.id, "message": "保存成功"}


@router.put("/api/visit_records/{record_id}")
@router.put("/api/communication/visit_records/{record_id}")
def update_visit_record(
    record_id: int,
    request: VisitRecordUpsertRequest,
    teacher: User = Depends(require_role("teacher")),
    db: Session = Depends(get_db),
) -> dict:
    record = (
        db.query(VisitRecord)
        .filter(VisitRecord.id == record_id, VisitRecord.teacher_id == teacher.id)
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")

    student = db.query(Student).filter(Student.id == request.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")

    record.student_id = request.student_id
    record.visit_date = request.visit_date
    record.content = request.content.strip()
    record.notes = request.notes.strip()
    db.commit()
    return {"id": record.id, "message": "更新成功"}


@router.get("/api/visit_records")
@router.get("/api/communication/visit_records")
def list_visit_records(
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    teacher: User = Depends(require_role("teacher")),
    db: Session = Depends(get_db),
) -> dict:
    query = (
        db.query(VisitRecord, Student)
        .join(Student, Student.id == VisitRecord.student_id)
        .filter(VisitRecord.teacher_id == teacher.id)
    )
    if start_date:
        query = query.filter(VisitRecord.visit_date >= start_date)
    if end_date:
        query = query.filter(VisitRecord.visit_date <= end_date)
    rows = query.order_by(VisitRecord.visit_date.desc(), VisitRecord.id.desc()).all()
    return {
        "items": [
            {
                "id": record.id,
                "student_id": student.id,
                "student_name": student.name,
                "visit_date": record.visit_date.isoformat(),
                "content": record.content,
                "notes": record.notes,
            }
            for record, student in rows
        ]
    }


@router.delete("/api/visit_records/{record_id}")
@router.delete("/api/communication/visit_records/{record_id}")
def delete_visit_record(
    record_id: int,
    teacher: User = Depends(require_role("teacher")),
    db: Session = Depends(get_db),
) -> dict:
    record = (
        db.query(VisitRecord)
        .filter(VisitRecord.id == record_id, VisitRecord.teacher_id == teacher.id)
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")
    db.delete(record)
    db.commit()
    return {"message": "删除成功"}


@router.get("/api/communication/visit_suggestion/{student_id}")
def get_visit_suggestion(
    student_id: str,
    teacher: User = Depends(require_role("teacher")),
    db: Session = Depends(get_db),
) -> dict:
    service = VisitSuggestionService(db)
    result = service.generate_for_student(student_id)
    if result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/api/communication/visit_target_suggestions")
def get_visit_target_suggestions(
    class_id: Optional[str] = Query(default=None),
    limit: int = Query(default=5, ge=1, le=20),
    teacher: User = Depends(require_role("teacher")),
    db: Session = Depends(get_db),
) -> dict:
    service = VisitSuggestionService(db)
    return service.suggest_targets(class_id=class_id or "", limit=limit)
