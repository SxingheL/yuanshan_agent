import json
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, TypedDict

from pydantic import BaseModel, Field

from backend.app.llm_config import llm_settings


class TimeBlock(BaseModel):
    time: str = Field(description="时间段，如 00:00 - 05:00")
    group: str = Field(description="a / b / all")
    label: str = Field(description="环节标题")
    desc: str = Field(description="具体教学描述")


class LessonPlanOutput(BaseModel):
    title: str
    plan: List[TimeBlock]
    self_study_tasks: Dict[str, str]


class LessonPlanState(TypedDict, total=False):
    group_a: str
    group_b: str
    subject: str
    duration: int
    topic: str
    examples: str
    prompt: str
    raw_text: str
    result: Dict[str, Any]


class LessonPlanGenerator:
    def __init__(self) -> None:
        self._graph = self._build_graph()

    async def generate(
        self,
        *,
        group_a: str,
        group_b: str,
        subject: str,
        duration: int,
        topic: str,
    ) -> Dict[str, Any]:
        state: LessonPlanState = {
            "group_a": group_a,
            "group_b": group_b,
            "subject": subject,
            "duration": duration,
            "topic": topic,
        }

        if self._graph:
            result = await self._graph.ainvoke(state)
            return result["result"]

        result = await self._run_pipeline(state)
        return result["result"]

    def _build_graph(self):
        try:
            from langgraph.graph import END, START, StateGraph
        except Exception:
            return None

        graph = StateGraph(LessonPlanState)
        graph.add_node("retrieve_examples", self._node_retrieve_examples)
        graph.add_node("compose_prompt", self._node_compose_prompt)
        graph.add_node("generate_plan", self._node_generate_plan)
        graph.add_edge(START, "retrieve_examples")
        graph.add_edge("retrieve_examples", "compose_prompt")
        graph.add_edge("compose_prompt", "generate_plan")
        graph.add_edge("generate_plan", END)
        return graph.compile()

    async def _run_pipeline(self, state: LessonPlanState) -> LessonPlanState:
        state.update(self._node_retrieve_examples(state))
        state.update(self._node_compose_prompt(state))
        state.update(await self._node_generate_plan(state))
        return state

    def _node_retrieve_examples(self, state: LessonPlanState) -> LessonPlanState:
        subject = state["subject"]
        return {"examples": self._load_examples(subject)}

    def _node_compose_prompt(self, state: LessonPlanState) -> LessonPlanState:
        prompt = f"""
你是山村复式教学专家。请根据以下要求生成一份精确到分钟的复式课堂教学方案。

【课堂参数】
- A组：{state['group_a']}
- B组：{state['group_b']}
- 学科：{state['subject']}
- 总时长：{state['duration']}分钟
- 课题：《{state['topic']}》

【要求】
1. 必须包含完整流程：全班导入 -> 课中分组轮转 -> 全班总结展示。
2. 时间分配精确到分钟。
3. A组与B组在轮转阶段必须有一组教师直教，另一组执行清晰、自主、可独立完成的任务单。
4. 内容要体现趣味性、主体性和课程标准意识。
5. 输出 JSON，包含 title、plan、self_study_tasks 三个字段。

【Few-shot 示例】
{state['examples']}
"""
        return {"prompt": prompt}

    async def _node_generate_plan(self, state: LessonPlanState) -> LessonPlanState:
        result = await self._generate_result(state)
        return {"result": result}

    async def _generate_result(self, state: LessonPlanState) -> Dict[str, Any]:
        if llm_settings.use_real_llm:
            llm_result = await self._generate_with_langchain(state["prompt"])
            if llm_result:
                return llm_result
        return self._generate_with_template(state)

    async def _generate_with_langchain(self, prompt: str) -> Dict[str, Any]:
        try:
            from langchain.prompts import ChatPromptTemplate
            from langchain_community.llms import Ollama
        except Exception:
            return {}

        try:
            llm = Ollama(
                model=llm_settings.ollama_model,
                base_url=llm_settings.ollama_base_url,
            )
            chain = ChatPromptTemplate.from_template("{prompt}") | llm
            text = await chain.ainvoke({"prompt": prompt})
            if isinstance(text, str):
                parsed = self._safe_parse_json(text)
                if parsed:
                    return self._normalize_result(parsed)
        except Exception:
            return {}
        return {}

    def _safe_parse_json(self, text: str) -> Dict[str, Any]:
        try:
            return json.loads(text)
        except Exception:
            match = re.search(r"\{[\s\S]*\}", text)
            if match:
                try:
                    return json.loads(match.group(0))
                except Exception:
                    return {}
        return {}

    def _normalize_result(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        created_at = datetime.now(timezone.utc).isoformat()
        return {
            "id": payload.get("id") or self._build_plan_id(),
            "title": payload.get("title", "复式课堂教学方案"),
            "plan": payload.get("plan", []),
            "self_study_tasks": payload.get("self_study_tasks", {}),
            "created_at": payload.get("created_at", created_at),
        }

    def _generate_with_template(self, state: LessonPlanState) -> Dict[str, Any]:
        topic = state["topic"]
        subject = state["subject"]
        group_a = state["group_a"]
        group_b = state["group_b"]
        duration = state["duration"]

        group_a_grade = self._extract_grade(group_a)
        group_b_grade = self._extract_grade(group_b)

        task_a = (
            f"1. 完成《{topic}》关键词描红或抄写。\n"
            f"2. 用自己的话说一说《{topic}》中最重要的一个画面。\n"
            "3. 完成后与同桌互读一遍，不打扰另一组上课。"
        )
        task_b = (
            f"1. 独立阅读《{topic}》相关段落并圈画关键词。\n"
            "2. 思考作者从哪些角度展开描写，并写下两个词。\n"
            "3. 完成后尝试把答案整理成2句话。"
        )

        plan = [
            {
                "time": "00:00 - 05:00",
                "group": "all",
                "label": "🌟 全班导入",
                "desc": f"围绕《{topic}》设置生活化导入，用图片、提问或情境故事激活两个年级的共同兴趣。",
            },
            {
                "time": "05:00 - 18:00",
                "group": "b",
                "label": f"📚 A组（{group_a_grade}）· 教师直教",
                "desc": f"教师带领A组聚焦本课核心内容，进行朗读、生字或关键概念讲解；B组同步执行自学任务单。",
            },
            {
                "time": "18:00 - 32:00",
                "group": "a",
                "label": f"📚 B组（{group_b_grade}）· 教师直教",
                "desc": f"教师转向B组讲解重难点、组织讨论与练习；A组回到自主任务或互助活动，保证安静完成。",
            },
            {
                "time": f"32:00 - {duration:02d}:00" if duration <= 59 else "32:00 - 40:00",
                "group": "all",
                "label": "🎉 全班汇报展示",
                "desc": "两个年级分别汇报学习结果，教师进行归纳总结，并点出今天各自的学习收获。",
            },
        ]

        created_at = datetime.now(timezone.utc).isoformat()
        return {
            "id": self._build_plan_id(),
            "title": f"复式课堂教学方案 · {subject}《{topic}》· {duration}分钟",
            "plan": plan,
            "self_study_tasks": {
                "group_a": task_a,
                "group_b": task_b,
            },
            "created_at": created_at,
        }

    def _build_plan_id(self) -> str:
        return f"plan_{int(time.time())}"

    def _extract_grade(self, text: str) -> str:
        match = re.search(r"([一二三四五六七八九十0-9]+年级)", text)
        return match.group(1) if match else text

    def _load_examples(self, subject: str) -> str:
        examples = {
            "语文": """
{
  "title": "复式课堂教学方案 · 语文《燕子》· 40分钟",
  "plan": [
    {"time": "00:00 - 05:00", "group": "all", "label": "全班导入", "desc": "从春天景象切入，激活学生生活经验。"},
    {"time": "05:00 - 18:00", "group": "b", "label": "A组教师直教", "desc": "三年级进行生字与朗读指导，五年级独立阅读并圈画关键词。"}
  ],
  "self_study_tasks": {
    "group_a": "描红生字并朗读课文一遍",
    "group_b": "圈画写景关键词并写下理解"
  }
}
""",
            "数学": """
{
  "title": "复式课堂教学方案 · 数学《认识分数》· 40分钟",
  "plan": [
    {"time": "00:00 - 05:00", "group": "all", "label": "全班导入", "desc": "用分苹果的情境引出分数。"},
    {"time": "05:00 - 18:00", "group": "b", "label": "A组教师直教", "desc": "教师讲解基础概念，另一组完成操作任务单。"}
  ],
  "self_study_tasks": {
    "group_a": "完成分一分练习",
    "group_b": "观察图形并写下分数"
  }
}
""",
        }
        return examples.get(subject, examples["语文"])
