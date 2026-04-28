from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from backend.app.auth import require_role
from backend.app.db.database import get_db
from backend.app.db.models import User
from backend.app.services.master_matcher import MasterMatcher
from backend.app.services.microcourse_service import (
    MicrocourseService,
    MicrocourseTaskStore,
    run_microcourse_task,
)


router = APIRouter(tags=["microcourse"])

ALLOWED_VIDEO_TYPES = {
    "video/mp4",
    "video/quicktime",
    "video/x-msvideo",
    "video/webm",
}
MAX_VIDEO_SIZE = 200 * 1024 * 1024


@router.post("/api/agent/microcourse_analysis")
async def upload_microcourse(
    background_tasks: BackgroundTasks,
    video: UploadFile = File(...),
    subject: str = Form(...),
    grade: str = Form(...),
    topic: str = Form(...),
    teacher: User = Depends(require_role("teacher")),
    db: Session = Depends(get_db),
) -> dict:
    if video.content_type and video.content_type not in ALLOWED_VIDEO_TYPES:
        raise HTTPException(status_code=400, detail="仅支持 mp4/mov/avi/webm 视频")
    video_bytes = await video.read()
    if len(video_bytes) > MAX_VIDEO_SIZE:
        raise HTTPException(status_code=400, detail="视频大小不能超过 200MB")
    if not video_bytes:
        raise HTTPException(status_code=400, detail="视频内容为空")

    task_id = MicrocourseService.generate_task_id()
    MicrocourseTaskStore.set(
        task_id,
        {"status": "processing", "message": "任务已提交，正在分析中"},
    )
    payload = {
        "filename": video.filename or "lesson.mp4",
        "content_type": video.content_type or "video/mp4",
        "content": video_bytes,
    }
    background_tasks.add_task(
        run_microcourse_task,
        task_id,
        payload,
        teacher.id,
        subject,
        grade,
        topic,
    )
    return {"task_id": task_id, "status": "processing"}


@router.get("/api/agent/microcourse_result/{task_id}")
def get_microcourse_result(
    task_id: str,
    teacher: User = Depends(require_role("teacher")),
) -> dict:
    result = MicrocourseTaskStore.get(task_id)
    if not result:
        return {"status": "pending"}
    return result


@router.get("/api/agent/master_lessons")
def list_master_lessons(
    subject: Optional[str] = Query(default=None),
    grade: Optional[str] = Query(default=None),
    topic: Optional[str] = Query(default=None),
    limit: int = Query(default=8, ge=1, le=20),
    teacher: User = Depends(require_role("teacher")),
    db: Session = Depends(get_db),
) -> dict:
    matcher = MasterMatcher(db)
    return {
        "items": matcher.list_links(
            subject=subject or "",
            grade=grade or "",
            topic=topic or "",
            limit=limit,
        )
    }
