import math
import re
from typing import Dict, List

from sqlalchemy.orm import Session

from backend.app.db.models import MasterLesson


def _tokenize(text: str) -> List[str]:
    return [t for t in re.split(r"[\s,，。；;：:（）()、]+", (text or "").lower()) if t]


class MasterMatcher:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.embed_model = None
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore

            self.embed_model = SentenceTransformer("BAAI/bge-small-zh-v1.5", device="cpu")
        except Exception:
            self.embed_model = None

    def match(self, subject: str, grade: str, topic: str) -> Dict:
        query_text = f"{subject} {grade} {topic}"
        candidates = (
            self.db.query(MasterLesson)
            .filter(MasterLesson.subject == subject)
            .order_by(MasterLesson.id.asc())
            .all()
        )
        if not candidates:
            candidates = self.db.query(MasterLesson).order_by(MasterLesson.id.asc()).all()
        if not candidates:
            raise ValueError("暂无名师课程资源")

        if self.embed_model:
            return self._vector_match(candidates, query_text)
        return self._keyword_match(candidates, query_text, topic)

    def list_links(self, subject: str = "", grade: str = "", topic: str = "", limit: int = 8) -> List[Dict]:
        query = self.db.query(MasterLesson)
        if subject:
            query = query.filter(MasterLesson.subject == subject)
        if grade:
            query = query.filter(MasterLesson.grade == grade)
        if topic:
            query = query.filter(MasterLesson.topic.contains(topic))
        rows = query.order_by(MasterLesson.id.desc()).limit(limit).all()
        return [
            {
                "id": row.id,
                "title": row.title,
                "url": row.url,
                "subject": row.subject,
                "grade": row.grade,
                "topic": row.topic,
                "description": row.description or "",
            }
            for row in rows
        ]

    def _vector_match(self, candidates: List[MasterLesson], query_text: str) -> Dict:
        import numpy as np  # type: ignore

        q = self.embed_model.encode(query_text)
        best = None
        best_score = -1.0
        for item in candidates:
            if item.embedding and isinstance(item.embedding, list) and len(item.embedding) == len(q):
                e = np.array(item.embedding, dtype=float)
            else:
                e = self.embed_model.encode(f"{item.subject} {item.grade} {item.topic} {item.title}")
            score = self._cosine(q, e)
            if score > best_score:
                best_score = score
                best = item
        return {
            "id": best.id,
            "title": best.title,
            "url": best.url,
            "transcript": best.transcript_text or "",
            "grade": best.grade,
            "subject": best.subject,
            "similarity": round(float(best_score), 4),
        }

    def _keyword_match(self, candidates: List[MasterLesson], query_text: str, topic: str) -> Dict:
        q_tokens = set(_tokenize(query_text))
        best = None
        best_score = -1
        for item in candidates:
            corpus = f"{item.subject} {item.grade} {item.topic} {item.title} {item.description or ''}"
            tokens = set(_tokenize(corpus))
            score = len(q_tokens & tokens)
            if topic and topic in item.topic:
                score += 3
            if score > best_score:
                best_score = score
                best = item
        return {
            "id": best.id,
            "title": best.title,
            "url": best.url,
            "transcript": best.transcript_text or "",
            "grade": best.grade,
            "subject": best.subject,
            "similarity": float(best_score),
        }

    def _cosine(self, a, b) -> float:
        import numpy as np  # type: ignore

        a = np.array(a, dtype=float)
        b = np.array(b, dtype=float)
        denom = (np.linalg.norm(a) * np.linalg.norm(b)) or 1.0
        return float(np.dot(a, b) / denom)
