import math
import random
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.db.models import Analogy, DialectMap, KnowledgePoint


def _tokenize(text: str) -> List[str]:
    text = (text or "").lower()
    return [token for token in re.split(r"[\s,，。？?！!、:：；;（）()]+", text) if token]


class KnowledgeRetriever:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._vector_enabled = False
        self._collection = None
        self._dialect_cache = self._load_dialect_map()
        self._try_init_vector_store()

    def normalize_query(self, query: str) -> str:
        normalized = query
        for dialect_word, mandarin_word in self._dialect_cache.items():
            normalized = normalized.replace(dialect_word, mandarin_word)
        return normalized.strip()

    def search(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        normalized_query = self.normalize_query(query)
        if self._vector_enabled and self._collection is not None:
            try:
                result = self._collection.query(query_texts=[normalized_query], n_results=top_k)
                rows = []
                ids = result.get("ids", [[]])[0]
                metadatas = result.get("metadatas", [[]])[0]
                distances = result.get("distances", [[]])[0]
                for item_id, metadata, distance in zip(ids, metadatas, distances):
                    rows.append(
                        {
                            "id": int(item_id),
                            "metadata": metadata,
                            "score": 1 - float(distance),
                        }
                    )
                if rows:
                    return rows
            except Exception:
                self._vector_enabled = False

        return self._keyword_search(normalized_query, top_k)

    def get_analogy(self, knowledge_point_id: int, scenario: str = "农村") -> Optional[str]:
        rows = (
            self.db.query(Analogy)
            .filter(
                Analogy.knowledge_point_id == knowledge_point_id,
                Analogy.scenario.like(f"%{scenario}%"),
            )
            .all()
        )
        if rows:
            return random.choice(rows).analogy_text

        fallback_rows = (
            self.db.query(Analogy)
            .filter(Analogy.knowledge_point_id == knowledge_point_id)
            .all()
        )
        if fallback_rows:
            return random.choice(fallback_rows).analogy_text
        return None

    def get_index(self, subject: Optional[str] = None, grade: Optional[str] = None) -> List[Dict[str, Any]]:
        query = self.db.query(KnowledgePoint)
        if subject:
            query = query.filter(KnowledgePoint.subject == subject)
        if grade:
            query = query.filter(KnowledgePoint.grade == grade)

        points = query.order_by(KnowledgePoint.grade.asc(), KnowledgePoint.name.asc()).all()
        grouped: Dict[str, List[KnowledgePoint]] = defaultdict(list)
        for point in points:
            grouped[point.grade].append(point)

        result = []
        for grade_name, grade_points in grouped.items():
            result.append(
                {
                    "grade": grade_name,
                    "points": [
                        {
                            "id": point.id,
                            "name": point.name,
                            "subject": point.subject,
                            "example": point.example,
                        }
                        for point in grade_points
                    ],
                }
            )
        return result

    def _load_dialect_map(self) -> Dict[str, str]:
        rows = self.db.query(DialectMap).all()
        return {row.dialect_word: row.mandarin_word for row in rows}

    def _try_init_vector_store(self) -> None:
        try:
            import chromadb  # type: ignore
            from chromadb.utils import embedding_functions  # type: ignore
        except Exception:
            return

        try:
            client = chromadb.PersistentClient(path="./backend/knowledge_db")
            collection = client.get_or_create_collection(
                name="knowledge_points",
                embedding_function=embedding_functions.SentenceTransformerEmbeddingFunction(
                    model_name="BAAI/bge-small-zh-v1.5"
                ),
            )
            if collection.count() == 0:
                points = self.db.query(KnowledgePoint).all()
                if points:
                    collection.add(
                        ids=[str(point.id) for point in points],
                        documents=[
                            f"{point.subject} {point.grade} {point.name} {point.content} {point.example}"
                            for point in points
                        ],
                        metadatas=[
                            {
                                "name": point.name,
                                "content": point.content,
                                "example": point.example,
                                "subject": point.subject,
                                "grade": point.grade,
                            }
                            for point in points
                        ],
                    )
            self._collection = collection
            self._vector_enabled = True
        except Exception:
            self._vector_enabled = False
            self._collection = None

    def _keyword_search(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        points = self.db.query(KnowledgePoint).all()
        query_tokens = set(_tokenize(query))
        scored_rows = []
        for point in points:
            corpus = f"{point.subject} {point.grade} {point.name} {point.content} {point.example}"
            tokens = set(_tokenize(corpus))
            overlap = len(query_tokens & tokens)
            fuzzy_bonus = 0
            if point.name in query:
                fuzzy_bonus += 3
            if point.subject in query:
                fuzzy_bonus += 1
            score = overlap + fuzzy_bonus
            if score > 0:
                scored_rows.append(
                    {
                        "id": point.id,
                        "metadata": {
                            "name": point.name,
                            "content": point.content,
                            "example": point.example,
                            "subject": point.subject,
                            "grade": point.grade,
                        },
                        "score": float(score),
                    }
                )

        scored_rows.sort(key=lambda item: item["score"], reverse=True)
        return scored_rows[:top_k]
