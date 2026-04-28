from typing import Dict, List

from backend.app.services.local_llm import LocalLLM


class NoticeGenerator:
    def __init__(self) -> None:
        self.llm = LocalLLM()

    def generate(self, draft: str) -> Dict:
        draft = (draft or "").strip()
        if not draft:
            draft = "请家长关注孩子近期学习情况，并按时完成老师布置任务。"

        prompt = f"""
你是一名山村小学老师。请将下面内容改写成两种版本：
1) 简洁版：温暖、无教育术语、分行短句。
2) 图文版：提炼成2-4个短句并配emoji。
原始内容：{draft}
请输出JSON：
{{
  "simple_version":"...",
  "graphic_version":{{"text":"句1；句2","icons":["📌","📚"]}}
}}
""".strip()

        fallback = self._fallback(draft)
        raw = self.llm.generate(prompt, fallback_answer="")
        parsed = self._try_parse(raw)
        if parsed:
            return parsed
        return fallback

    def _fallback(self, draft: str) -> Dict:
        simple = (
            "各位家长您好！\n"
            f"{draft}\n"
            "请您帮助孩子按要求准备和复习，我们一起陪伴孩子进步。谢谢您的支持！"
        )
        return {
            "simple_version": simple,
            "graphic_version": {
                "text": "请关注本次通知；请协助孩子准备；如有困难及时联系老师",
                "icons": ["📌", "📚", "🤝"],
            },
        }

    def _try_parse(self, raw: str) -> Dict:
        import json
        import re

        if not raw:
            return {}
        text = raw.strip()
        try:
            data = json.loads(text)
            if "simple_version" in data and "graphic_version" in data:
                return data
        except Exception:
            pass

        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            return {}
        try:
            data = json.loads(m.group(0))
            if "simple_version" in data and "graphic_version" in data:
                return data
        except Exception:
            return {}
        return {}
