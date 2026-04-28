from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from backend.app.services.knowledge_retriever import KnowledgeRetriever
from backend.app.services.local_llm import LocalLLM


class QAEngine:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.retriever = KnowledgeRetriever(db)
        self.llm = LocalLLM()

    def answer(self, question: str, scenario: str = "农村") -> Dict[str, Any]:
        normalized_question = self.retriever.normalize_query(question)
        results = self.retriever.search(normalized_question, top_k=3)
        if not results:
            fallback = "这个问题我暂时还不会。您可以换一种问法，或者告诉我学科和年级，我再试着解释。"
            return {
                "answer": fallback,
                "matched_knowledge_point": None,
                "normalized_query": normalized_question,
                "source": "fallback",
                "related": [],
            }

        best = results[0]
        metadata = best["metadata"]
        analogy = self.retriever.get_analogy(best["id"], scenario=scenario)

        fallback_answer = self._build_grounded_answer(
            question=normalized_question,
            metadata=metadata,
            analogy=analogy,
        )
        prompt = self._build_prompt(
            question=normalized_question,
            metadata=metadata,
            analogy=analogy,
        )
        answer_text = self.llm.generate(prompt, fallback_answer=fallback_answer)

        return {
            "answer": answer_text,
            "matched_knowledge_point": {
                "id": best["id"],
                "name": metadata.get("name", ""),
                "subject": metadata.get("subject", ""),
                "grade": metadata.get("grade", ""),
            },
            "normalized_query": normalized_question,
            "source": "local_llm" if answer_text != fallback_answer else "template",
            "related": [
                {
                    "id": item["id"],
                    "name": item["metadata"].get("name", ""),
                    "grade": item["metadata"].get("grade", ""),
                }
                for item in results[1:]
            ],
        }

    def _build_prompt(
        self,
        question: str,
        metadata: Dict[str, Any],
        analogy: Optional[str],
    ) -> str:
        return f"""
你是一位山村小学的离线AI助教。你的回答必须：
- 用农村孩子能听懂的例子，比如分馍、赶集、种地、喂鸡、收玉米
- 语言温暖、耐心，不要堆砌术语
- 如果涉及计算，按步骤讲清楚

知识点：{metadata.get('name', '')}
学科：{metadata.get('subject', '')}
年级：{metadata.get('grade', '')}
标准解释：{metadata.get('content', '')}
标准例题：{metadata.get('example', '')}
参考类比：{analogy or '无'}

老师问题：{question}

请生成一段自然、清楚、带本地化类比的回答：
""".strip()

    def _build_grounded_answer(
        self,
        question: str,
        metadata: Dict[str, Any],
        analogy: Optional[str],
    ) -> str:
        name = metadata.get("name", "")
        content = metadata.get("content", "")
        example = metadata.get("example", "")
        lines = [
            f"这个问题主要是在问“{name}”。",
            content,
        ]
        if analogy:
            lines.append(f"可以这样给孩子讲：{analogy}")
        if example:
            lines.append(f"再举个小例子：{example}")
        lines.append("讲的时候先说生活里的画面，再慢慢回到书本上的说法，孩子会更容易听懂。")
        return "\n".join(lines)
