from datetime import date
from typing import Any, Dict, List, Optional
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.auth import require_role
from backend.app.db.database import SessionLocal, get_db
from backend.app.db.models import Student, User
from backend.app.services.homework_corrector import HomeworkCorrector, HomeworkTaskStore


router = APIRouter(tags=["homework"])


class ManualEntryItem(BaseModel):
    student_id: str
    score: float
    completion_rate: float = 1.0
    wrong_knowledge_points: List[str] = []
    answers: List[Dict[str, Any]] = []


class ManualEntryRequest(BaseModel):
    class_id: str
    subject: str
    homework_id: Optional[str] = None
    date: Optional[str] = None
    entries: List[ManualEntryItem]


def run_homework_task(
    task_id: str,
    file_payloads: List[Dict[str, Any]],
    class_id: str,
    subject: str,
    teacher_id: int,
    homework_id: Optional[str],
    date_value: Optional[str],
) -> None:
    db = SessionLocal()
    try:
        corrector = HomeworkCorrector(db)
        corrector.process_batch_sync(
            task_id=task_id,
            files=file_payloads,
            class_id=class_id,
            subject=subject,
            teacher_id=teacher_id,
            homework_id=homework_id,
            homework_date=date_value,
        )
    finally:
        db.close()


@router.post("/api/agent/homework_correction")
async def start_homework_correction(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    class_id: str = Form(...),
    subject: str = Form(...),
    homework_id: Optional[str] = Form(None),
    date_value: Optional[str] = Form(None, alias="date"),
    teacher: User = Depends(require_role("teacher")),
) -> dict:
    task_id = f"corr_{uuid.uuid4().hex[:8]}"
    file_payloads = []
    for file in files:
        content = await file.read()
        file_payloads.append(
            {
                "filename": file.filename or "homework.jpg",
                "content_type": file.content_type,
                "content": content,
            }
        )

    HomeworkTaskStore.set(
        task_id,
        {
            "task_id": task_id,
            "status": "processing",
            "message": "作业已提交，正在处理中，请稍后查询结果",
        },
    )
    background_tasks.add_task(
        run_homework_task,
        task_id,
        file_payloads,
        class_id,
        subject,
        teacher.id,
        homework_id,
        date_value,
    )
    return {
        "task_id": task_id,
        "status": "processing",
        "message": f"{teacher.full_name}老师，作业已提交，正在处理中，请稍后查询结果。",
    }


@router.get("/api/agent/homework_result/{task_id}")
def get_homework_result(
    task_id: str,
    teacher: User = Depends(require_role("teacher")),
) -> dict:
    result = HomeworkTaskStore.get(task_id)
    if not result:
        return {
            "task_id": task_id,
            "status": "pending",
            "message": f"{teacher.full_name}老师，任务仍在排队或处理中。",
        }
    return result


@router.post("/api/homework/manual_entry")
def manual_entry(
    req: ManualEntryRequest,
    teacher: User = Depends(require_role("teacher")),
    db: Session = Depends(get_db),
) -> dict:
    corrector = HomeworkCorrector(db)
    homework_date = corrector._parse_date(req.date)
    homework_id = req.homework_id or f"{teacher.id}_{req.class_id}_{req.subject}_{homework_date.strftime('%Y%m%d')}_manual"
    students = (
        db.query(Student)
        .filter(Student.class_id == req.class_id)
        .order_by(Student.name.asc())
        .all()
    )
    student_ids = {student.id for student in students}

    results = []
    for entry in req.entries:
        if entry.student_id not in student_ids:
            continue
        student = db.query(Student).filter(Student.id == entry.student_id).first()
        results.append(
            {
                "student_id": entry.student_id,
                "student_name": student.name if student else entry.student_id,
                "score": entry.score,
                "completion_rate": entry.completion_rate,
                "wrong_knowledge_points": entry.wrong_knowledge_points,
                "answers": entry.answers,
            }
        )

    submitted_ids = {item["student_id"] for item in results}
    unsubmitted_students = [student for student in students if student.id not in submitted_ids]
    summary = corrector.aggregate_stats(
        results,
        total_students=len(students),
        unsubmitted_count=len(unsubmitted_students),
    )
    corrector.save_to_database(
        homework_id=homework_id,
        class_id=req.class_id,
        subject=req.subject,
        homework_date=homework_date,
        results=results,
        unsubmitted_students=unsubmitted_students,
        summary=summary,
    )
    alerts = corrector.check_continuous_errors(results)
    return {
        "status": "completed",
        "homework_id": homework_id,
        "summary": summary,
        "alerts": alerts,
        "message": f"{teacher.full_name}老师，本次手动录入已完成。",
    }
