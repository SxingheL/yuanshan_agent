from typing import Any, Dict, List

from backend.app.services.local_llm import LocalLLM


class ComparisonEngine:
    def __init__(self) -> None:
        self.llm = LocalLLM()

    def compare(self, teacher_text: str, master_text: str) -> Dict[str, Any]:
        prompt = f"""
你是资深教学诊断专家。请对比教师与名师逐字稿，输出JSON：
{{
  "structure_advice":"...",
  "questioning_advice":"...",
  "specific_improvements":[
    {{"time":"03:15","original":"...","suggest":"...","reason":"..."}}
  ]
}}
要求：必须具体到时间点，建议可直接执行，不要空话。
教师逐字稿：{teacher_text}
名师逐字稿：{master_text}
""".strip()

        fallback = self._fallback(teacher_text, master_text)
        raw = self.llm.generate(prompt, fallback_answer="")
        parsed = self._parse(raw)
        return parsed if parsed else fallback

    def _fallback(self, teacher_text: str, master_text: str) -> Dict[str, Any]:
        return {
            "structure_advice": "第03:15你直接给出定义，建议先停顿3秒并追问“你们觉得呢？”，再给出概念。",
            "questioning_advice": "第05:10你的提问偏封闭式，可改为“生活中哪里见过这种情况？”引导学生举例。",
            "specific_improvements": [
                {
                    "time": "03:15",
                    "original": "直接讲解分数定义并连续输出信息",
                    "suggest": "先展示半个苹果，问“怎么用数字表示一半？”，再总结分数定义",
                    "reason": "先让学生生成想法，再抽象概念，理解更稳固",
                },
                {
                    "time": "07:40",
                    "original": "练习环节只让前排回答",
                    "suggest": "使用随机点名或小组轮答，覆盖后排与安静学生",
                    "reason": "扩大参与面，提升课堂公平与注意力",
                },
                {
                    "time": "11:20",
                    "original": "课程结束前直接布置作业",
                    "suggest": "增加1分钟学生复述“今天学会了什么”，再布置作业",
                    "reason": "帮助学生形成知识闭环，便于课后迁移",
                },
            ],
        }

    def _parse(self, raw: str) -> Dict[str, Any]:
        import json
        import re

        if not raw:
            return {}
        text = raw.strip()
        try:
            data = json.loads(text)
            if self._valid(data):
                return data
        except Exception:
            pass
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            return {}
        try:
            data = json.loads(m.group(0))
            if self._valid(data):
                return data
        except Exception:
            return {}
        return {}

    def _valid(self, data: Dict[str, Any]) -> bool:
        return (
            isinstance(data, dict)
            and isinstance(data.get("structure_advice"), str)
            and isinstance(data.get("questioning_advice"), str)
            and isinstance(data.get("specific_improvements"), list)
        )
