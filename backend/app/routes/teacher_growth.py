from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.auth import require_role
from backend.app.db.database import get_db
from backend.app.db.models import User
from backend.app.services.badge_service import BadgeService
from backend.app.services.teacher_stats import TeacherStatsService
from backend.app.services.title_material_generator import TitleMaterialGenerator


router = APIRouter(prefix="/api/teacher", tags=["teacher-growth"])


class TitleRequest(BaseModel):
    format: str = "docx"
    include_appendix: bool = True


@router.get("/growth_archive")
def get_growth_archive(
    teacher: User = Depends(require_role("teacher")),
    db: Session = Depends(get_db),
) -> dict:
    stats_service = TeacherStatsService(db, teacher.id)
    data = stats_service.compute_all_stats(force_refresh=False)

    badge_service = BadgeService(db, teacher.id)
    badge_service.check_and_update_badges()
    badges = badge_service.get_user_badges_with_progress()

    return {
        "stats": data["stats"],
        "five_dimensions": data["five_dimensions"],
        "badges": badges,
    }


@router.post("/refresh_stats")
def refresh_stats(
    teacher: User = Depends(require_role("teacher")),
    db: Session = Depends(get_db),
) -> dict:
    stats_service = TeacherStatsService(db, teacher.id)
    stats_service.compute_all_stats(force_refresh=True)
    badge_service = BadgeService(db, teacher.id)
    new_badges = badge_service.check_and_update_badges()
    return {"message": "统计已刷新", "new_badges": new_badges}


@router.post("/generate_title_material")
def generate_title_material(
    req: TitleRequest,
    teacher: User = Depends(require_role("teacher")),
    db: Session = Depends(get_db),
) -> Response:
    generator = TitleMaterialGenerator(db, teacher.id)
    format_name = (req.format or "docx").lower()

    if format_name == "docx":
        try:
            buffer = generator.generate_docx(include_appendix=req.include_appendix)
        except Exception:
            raise HTTPException(status_code=400, detail="当前环境未安装 Word 导出依赖")
        return Response(
            content=buffer.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Content-Disposition": f"attachment; filename=title_material_{teacher.id}.docx"
            },
        )

    if format_name == "pdf":
        try:
            buffer = generator.generate_pdf(include_appendix=req.include_appendix)
        except Exception:
            raise HTTPException(status_code=400, detail="当前环境未安装 PDF 导出依赖")
        return Response(
            content=buffer.getvalue(),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=title_material_{teacher.id}.pdf"
            },
        )

    raise HTTPException(status_code=400, detail="仅支持 docx 或 pdf")
