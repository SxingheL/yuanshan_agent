from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.auth import require_role
from backend.app.db.database import get_db
from backend.app.db.models import CareerTemplate, Student, StudentDream, User
from backend.app.services.custom_career import CustomCareerGenerator
from backend.app.services.illustration_generator import IllustrationGenerator
from backend.app.services.story_engine import StoryEngine


router = APIRouter(prefix="/api/dream", tags=["dream"])


class StartRequest(BaseModel):
    student_id: Optional[str] = None
    career_id: Optional[int] = None
    custom_career: Optional[str] = None


class ChoiceRequest(BaseModel):
    student_id: Optional[str] = None
    dream_id: int
    choice_index: int


class IllustrationRequest(BaseModel):
    career_name: str
    scene: str = ""
    narration: str = ""


def resolve_student(db: Session, current_user: User, student_id: Optional[str]) -> Student:
    student = None
    if student_id:
        student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        student = db.query(Student).filter(Student.name == current_user.full_name).first()
    if not student:
        student = db.query(Student).order_by(Student.id.asc()).first()
    if not student:
        raise HTTPException(status_code=404, detail="未找到学生档案")
    return student


@router.get("/profile")
def get_dream_profile(
    current_user: User = Depends(require_role("student")),
    db: Session = Depends(get_db),
) -> dict:
    student = resolve_student(db, current_user, None)
    return {
        "student_id": student.id,
        "student_name": student.name,
        "grade": student.grade,
        "class_id": student.class_id,
    }


@router.get("/careers")
def list_careers(
    student_id: Optional[str] = Query(default=None),
    current_user: User = Depends(require_role("student")),
    db: Session = Depends(get_db),
) -> list:
    student = resolve_student(db, current_user, student_id)
    builtin = db.query(CareerTemplate).filter(CareerTemplate.is_custom.is_(False)).all()
    custom = (
        db.query(CareerTemplate)
        .filter(CareerTemplate.is_custom.is_(True), CareerTemplate.created_by == student.id)
        .all()
    )
    rows = builtin + custom
    return [
        {
            "id": row.id,
            "name": row.name,
            "icon": row.icon,
            "color": row.color,
            "description": row.description,
            "is_custom": bool(row.is_custom),
        }
        for row in rows
    ]


@router.post("/start")
def start_dream(
    req: StartRequest,
    current_user: User = Depends(require_role("student")),
    db: Session = Depends(get_db),
) -> dict:
    student = resolve_student(db, current_user, req.student_id)
    if not req.career_id and not req.custom_career:
        raise HTTPException(status_code=400, detail="career_id 与 custom_career 至少提供一个")

    career = None
    if req.custom_career:
        career_name = req.custom_career.strip()
        if not career_name:
            raise HTTPException(status_code=400, detail="自定义职业名称不能为空")
        generator = CustomCareerGenerator()
        existed = (
            db.query(CareerTemplate)
            .filter(
                CareerTemplate.is_custom.is_(True),
                CareerTemplate.created_by == student.id,
                CareerTemplate.name == career_name,
            )
            .first()
        )
        if existed:
            career = existed
            stories = career.stories if isinstance(career.stories, list) else []
            if len(stories) < 8:
                tpl = generator.generate_template(career_name, student.grade)
                career.description = tpl.get("description", "")
                career.skills = tpl.get("skills", [])
                career.stories = tpl.get("stories", [])
                career.knowledge_map = tpl.get("knowledge_map", [])
                career.sample_paths = tpl.get("sample_paths", [])
                db.commit()
                db.refresh(career)
        else:
            tpl = generator.generate_template(career_name, student.grade)
            career = CareerTemplate(
                name=career_name,
                icon="✨",
                color="#F0E8FC",
                description=tpl.get("description", ""),
                skills=tpl.get("skills", []),
                stories=tpl.get("stories", []),
                knowledge_map=tpl.get("knowledge_map", []),
                sample_paths=tpl.get("sample_paths", []),
                is_custom=True,
                created_by=student.id,
            )
            db.add(career)
            db.commit()
            db.refresh(career)
    else:
        career = db.query(CareerTemplate).filter(CareerTemplate.id == req.career_id).first()
        if not career:
            raise HTTPException(status_code=404, detail="职业模板不存在")

    stories = career.stories or []
    if not stories:
        raise HTTPException(status_code=400, detail="职业模板缺少故事节点")
    dream = StudentDream(
        student_id=student.id,
        career_id=career.id,
        custom_career_name=req.custom_career or "",
        story_progress=[],
        earned_skills=[],
        generated_path={},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(dream)
    db.commit()
    db.refresh(dream)
    return {
        "dream_id": dream.id,
        "career": {"id": career.id, "name": career.name, "icon": career.icon},
        "story_total": len(stories),
        "first_node": stories[0],
    }


@router.post("/choose")
def make_choice(
    req: ChoiceRequest,
    current_user: User = Depends(require_role("student")),
    db: Session = Depends(get_db),
) -> dict:
    student = resolve_student(db, current_user, req.student_id)
    dream = db.query(StudentDream).filter(StudentDream.id == req.dream_id).first()
    if not dream or dream.student_id != student.id:
        raise HTTPException(status_code=404, detail="梦想记录不存在")
    engine = StoryEngine(db)
    try:
        return engine.get_next_node(req.dream_id, req.choice_index)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/path")
def get_path(
    dream_id: int,
    student_id: Optional[str] = Query(default=None),
    current_user: User = Depends(require_role("student")),
    db: Session = Depends(get_db),
) -> dict:
    student = resolve_student(db, current_user, student_id)
    dream = db.query(StudentDream).filter(StudentDream.id == dream_id).first()
    if not dream or dream.student_id != student.id:
        raise HTTPException(status_code=404, detail="梦想记录不存在")
    if dream.generated_path:
        return dream.generated_path
    career = db.query(CareerTemplate).filter(CareerTemplate.id == dream.career_id).first()
    if not career:
        raise HTTPException(status_code=404, detail="职业模板不存在")
    stories = career.stories or []
    if len(dream.story_progress or []) < len(stories):
        raise HTTPException(status_code=400, detail="路径尚未生成，请完成所有故事选择")
    engine = StoryEngine(db)
    return engine.generate_final_path(dream, career)


@router.post("/illustration")
def generate_illustration(
    req: IllustrationRequest,
    current_user: User = Depends(require_role("student")),
) -> dict:
    _ = current_user
    service = IllustrationGenerator()
    data = service.generate(req.career_name.strip() or "职业探索", req.scene, req.narration)
    return data
