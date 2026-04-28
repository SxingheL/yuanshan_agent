from typing import Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from backend.app.auth import get_current_user_optional
from backend.app.db.database import get_db
from backend.app.db.models import User
from backend.app.services.asr import OfflineASR
from backend.app.services.qa_engine import QAEngine
from backend.app.services.knowledge_retriever import KnowledgeRetriever


router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])
asr_service = OfflineASR()


@router.post("/chat")
def chat(
    query: str = Form(...),
    scenario: str = Form("农村"),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
) -> dict:
    engine = QAEngine(db)
    result = engine.answer(query, scenario=scenario)
    return {
        "answer": result["answer"],
        "matched_knowledge_point": result["matched_knowledge_point"],
        "normalized_query": result["normalized_query"],
        "source": result["source"],
        "related": result["related"],
        "user": current_user.full_name if current_user else "老师",
    }


@router.post("/voice_chat")
async def voice_chat(
    audio: UploadFile = File(...),
    scenario: str = Form("农村"),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
) -> dict:
    audio_bytes = await audio.read()
    text = asr_service.transcribe(audio_bytes)
    engine = QAEngine(db)
    result = engine.answer(text, scenario=scenario)
    return {
        "text": text,
        "answer": result["answer"],
        "matched_knowledge_point": result["matched_knowledge_point"],
        "source": result["source"],
        "user": current_user.full_name if current_user else "老师",
    }


@router.get("/index/knowledge_points")
def get_knowledge_points(
    subject: Optional[str] = None,
    grade: Optional[str] = None,
    db: Session = Depends(get_db),
) -> dict:
    retriever = KnowledgeRetriever(db)
    return {
        "subject": subject,
        "grade": grade,
        "items": retriever.get_index(subject=subject, grade=grade),
    }
