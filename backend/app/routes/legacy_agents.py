from typing import Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel

from backend.app.auth import get_current_user, get_current_user_optional, require_role
from backend.app.db.models import User


router = APIRouter(tags=["legacy-agents"])


class ChatRequest(BaseModel):
    query: str
    subject: Optional[str] = "通用"


class NoticeRequest(BaseModel):
    draft: str
    is_voice: bool = False


class DreamStepRequest(BaseModel):
    career_id: str
    current_node: str
    chosen_option: str


@router.post("/api/agent/chat_knowledge")
def chat_knowledge(
    request: ChatRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
) -> dict:
    if "分数除法" in request.query:
        reply = "分数除法可以理解成把已经分好的东西再继续平均分一次，讲的时候可以用分地、分玉米来举例。"
    elif "进位加法" in request.query:
        reply = "进位加法像赶集凑整钱：个位满十就往前一位送一个。"
    else:
        reply = f"{current_user.full_name if current_user else '老师'}，建议用田地、赶集、粮食分配这类孩子熟悉的场景来讲。"
    return {"status": "success", "reply": reply}


@router.post("/api/agent/generate_notice")
def generate_notice(
    request: NoticeRequest,
    current_user: User = Depends(require_role("teacher")),
) -> dict:
    return {
        "status": "success",
        "text_version": f"各位家长您好！\n{request.draft}\n请大家配合，谢谢！",
        "graphic_version": [
            {"icon": "📌", "text": "请关注本次通知重点"},
            {"icon": "📝", "text": "请协助孩子按要求完成"},
        ],
    }


@router.post("/api/legacy/microcourse_analysis")
def analyze_microcourse(
    video: UploadFile = File(...),
    subject: str = Form(...),
    topic: str = Form(...),
    current_user: User = Depends(require_role("teacher")),
) -> dict:
    return {
        "status": "success",
        "advantages": [
            "第8分钟的本地化举例很生动，孩子容易产生联想。",
            "板书清晰，层次分明，便于学生跟上思路。",
        ],
        "improvements": [
            "建议1 (02:47)：概念讲解后增加停顿和追问，让学生有思考时间。",
            "建议2 (11:23)：练习环节扩大点名覆盖面，照顾后排和安静学生。",
            "建议3 (结构)：最后增加学生复述总结，提高课堂闭环感。",
        ],
        "scores": {"intro": 9, "explain": 7, "practice": 6, "summary": 3, "total": 7.0},
    }


@router.post("/api/agent/dream_simulator")
def dream_simulator_step(
    request: DreamStepRequest,
    current_user: User = Depends(get_current_user),
) -> dict:
    feedback = f"✅ 你选择了【{request.chosen_option}】。\n你又向梦想前进了一步。"
    if "直接上前" in request.chosen_option or "假装" in request.chosen_option:
        feedback = f"⚠️ 这次选择有点冒险，但你学到了做决定前要先观察。"
    return {
        "status": "success",
        "feedback": feedback,
        "next_scene": "接下来出现了一个新的挑战，需要你继续思考。",
        "options": ["先观察周围情况", "找有经验的人请教", "自己先试一个安全的小办法"],
    }


@router.get("/api/teacher/growth")
def get_teacher_growth(current_user: User = Depends(require_role("teacher"))) -> dict:
    return {
        "status": "success",
        "teacher": current_user.full_name,
        "growth_curve": [72, 75, 79, 83, 87],
        "medals": ["连续30天备课达人", "本月互助之星"],
    }


@router.get("/api/student/archive")
def get_student_archive(current_user: User = Depends(require_role("student", "teacher"))) -> dict:
    return {
        "status": "success",
        "student_name": current_user.full_name if current_user.role == "student" else "王小明",
        "learning": {"math": "稳步提升", "chinese": "表现良好"},
        "tasks": ["完成本周数学作业", "读一篇关于太空的短文"],
    }
