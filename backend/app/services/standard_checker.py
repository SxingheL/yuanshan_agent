import re
from typing import Any, Dict, List

from backend.app.llm_config import llm_settings


class StandardChecker:
    def __init__(self) -> None:
        self._rule_bank = {
            "语文": [
                ("识字写字", [r"生字", r"描红", r"抄写", r"字词"]),
                ("朗读感悟", [r"朗读", r"诵读", r"阅读", r"圈画关键词"]),
                ("理解表达", [r"思考", r"交流", r"汇报", r"总结"]),
                ("写作练笔", [r"仿写", r"练笔", r"写一写"]),
            ],
            "数学": [
                ("概念理解", [r"概念", r"分一分", r"观察"]),
                ("操作体验", [r"操作", r"动手", r"活动"]),
                ("练习巩固", [r"练习", r"计算", r"巩固"]),
                ("迁移应用", [r"生活", r"应用", r"解决问题"]),
            ],
        }

    async def check(
        self,
        *,
        subject: str,
        grade: str,
        topic: str,
        plan_text: str,
    ) -> Dict[str, Any]:
        if llm_settings.use_real_llm:
            llm_result = await self._check_with_llm(subject, grade, topic, plan_text)
            if llm_result:
                return llm_result
        return self._check_with_rules(subject, grade, topic, plan_text)

    async def _check_with_llm(
        self,
        subject: str,
        grade: str,
        topic: str,
        plan_text: str,
    ) -> Dict[str, Any]:
        try:
            from langchain_community.llms import Ollama
        except Exception:
            return {}

        prompt = f"""
请根据《义务教育{subject}课程标准（2022年版）》检查以下教学方案对{grade}{topic}相关课程标准的覆盖情况。

教学方案：
{plan_text}

请输出JSON格式：
{{
  "coverage_percent": 85,
  "items": [
    {{"standard": "识字写字", "status": "covered", "comment": "..."}}
  ],
  "suggestions": "..."
}}
"""
        try:
            llm = Ollama(
                model=llm_settings.ollama_model,
                base_url=llm_settings.ollama_base_url,
            )
            text = await llm.ainvoke(prompt)
            if isinstance(text, str):
                import json

                match = re.search(r"\{[\s\S]*\}", text)
                if match:
                    return json.loads(match.group(0))
        except Exception:
            return {}
        return {}

    def _check_with_rules(
        self,
        subject: str,
        grade: str,
        topic: str,
        plan_text: str,
    ) -> Dict[str, Any]:
        rules = self._rule_bank.get(subject, self._rule_bank["语文"])
        items: List[Dict[str, str]] = []
        covered = 0

        for standard_name, patterns in rules:
            hits = sum(1 for pattern in patterns if re.search(pattern, plan_text))
            if hits >= 2:
                items.append(
                    {
                        "standard": standard_name,
                        "status": "covered",
                        "comment": f"{standard_name}相关环节较完整，方案中有明确体现。",
                    }
                )
                covered += 1
            elif hits == 1:
                items.append(
                    {
                        "standard": standard_name,
                        "status": "partial",
                        "comment": f"{standard_name}已有设计，但建议再补充更明确的活动或产出。",
                    }
                )
                covered += 0.5
            else:
                items.append(
                    {
                        "standard": standard_name,
                        "status": "missing",
                        "comment": f"当前方案中对{standard_name}体现不明显，建议补充。",
                    }
                )

        coverage_percent = int((covered / max(len(rules), 1)) * 100)
        suggestions = self._build_suggestion(items, subject, grade, topic)

        return {
            "coverage_percent": coverage_percent,
            "items": items,
            "suggestions": suggestions,
        }

    def _build_suggestion(
        self,
        items: List[Dict[str, str]],
        subject: str,
        grade: str,
        topic: str,
    ) -> str:
        partial_or_missing = [item["standard"] for item in items if item["status"] != "covered"]
        if not partial_or_missing:
            return f"{grade}{subject}《{topic}》方案覆盖较完整，可进一步增强课堂趣味性与学生表达机会。"
        return "建议优先补充：" + "、".join(partial_or_missing) + "。可在结尾加入小练笔、复述或迁移应用环节。"
