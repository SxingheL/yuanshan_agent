import json
from typing import Dict

from backend.app.services.local_llm import LocalLLM


class FlashPolisher:
    def __init__(self) -> None:
        self.llm = LocalLLM()

    def polish(self, original: str) -> Dict[str, str]:
        prompt = f"""
你是一位温暖的小学老师。请将下列教师记录改写为“闪光时刻”，并给一句鼓励话。
必须输出JSON：
{{
  "polished":"润色后的描述（不超过50字）",
  "encouragement":"鼓励的话（不超过30字）"
}}
教师原始记录：{original}
要求：具体、积极、真实，不夸大。
""".strip()
        fallback = {
            "polished": self._fallback_polish(original),
            "encouragement": "勇敢尝试就是进步，老师为你点赞！",
        }
        raw = self.llm.generate(prompt, fallback_answer=json.dumps(fallback, ensure_ascii=False))
        parsed = self._parse_json(raw)
        data = parsed if parsed else fallback
        polished = str(data.get("polished", "") or "").strip()[:60]
        encouragement = str(data.get("encouragement", "") or "").strip()[:40]
        if not polished:
            polished = fallback["polished"]
        if not encouragement:
            encouragement = fallback["encouragement"]
        return {"polished": polished, "encouragement": encouragement}

    def _parse_json(self, raw: str) -> Dict:
        if not raw:
            return {}
        text = raw.strip()
        try:
            data = json.loads(text)
            return data if isinstance(data, dict) else {}
        except Exception:
            pass
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                data = json.loads(text[start : end + 1])
                return data if isinstance(data, dict) else {}
            except Exception:
                return {}
        return {}

    def _fallback_polish(self, original: str) -> str:
        text = (original or "").strip()
        if not text:
            return "今天你认真完成了一次学习挑战，值得肯定。"
        if len(text) > 50:
            text = text[:50]
        if "虽然" in text and "但是" in text:
            return text.replace("但是", "更可贵的是")
        return text
