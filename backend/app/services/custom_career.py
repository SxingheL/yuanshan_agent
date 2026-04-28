import json
from typing import Any, Dict

from backend.app.services.local_llm import LocalLLM


class CustomCareerGenerator:
    def __init__(self) -> None:
        self.llm = LocalLLM()

    def generate_template(self, career_name: str, student_grade: str) -> Dict[str, Any]:
        prompt = f"""
你是一位职业启蒙导师。请为梦想成为“{career_name}”的{student_grade}学生，生成职业体验模板。
必须输出 JSON，字段如下：
{{
  "description":"职业简介",
  "skills":["技能1","技能2","技能3"],
  "stories":[
    {{
      "scene":"第一章标题",
      "narration":"故事背景",
      "question":"问题",
      "choices":["A","B","C"],
      "feedback":["反馈A","反馈B","反馈C"]
    }}
  ],
  "knowledge_map":[
    {{"subject":"学科","link":"学科与职业关系","grade_recommend":"年级建议"}}
  ],
  "sample_paths":[
    {{"name":"🎓 大学（推荐）","steps":["步骤1","步骤2","步骤3"]}},
    {{"name":"💪 实践+进修","steps":["步骤1","步骤2","步骤3"]}},
    {{"name":"🌟 跨界发展","steps":["步骤1","步骤2","步骤3"]}}
  ]
}}
要求：
1. 使用鼓励、积极语气，适配中小学生理解。
2. 不要输出“辍学打工”等负向建议，强调继续教育与终身学习。
3. stories 至少8个节点，每个节点3个选项。
""".strip()
        fallback = self._fallback(career_name, student_grade)
        raw = self.llm.generate(prompt, fallback_answer=json.dumps(fallback, ensure_ascii=False))
        parsed = self._parse(raw)
        data = parsed if parsed else fallback
        return self._sanitize_template(data, career_name, student_grade)

    def _parse(self, raw: str) -> Dict[str, Any]:
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

    def _sanitize_template(self, data: Dict[str, Any], career_name: str, grade: str) -> Dict[str, Any]:
        description = str(data.get("description", "") or "").replace("辍学", "继续学习")
        skills = data.get("skills") if isinstance(data.get("skills"), list) else []
        stories = data.get("stories") if isinstance(data.get("stories"), list) else []
        knowledge_map = data.get("knowledge_map") if isinstance(data.get("knowledge_map"), list) else []
        sample_paths = data.get("sample_paths") if isinstance(data.get("sample_paths"), list) else []

        if len(stories) < 8:
            stories = self._fallback(career_name, grade)["stories"]
        stories = self._ensure_min_story_nodes(stories, career_name, min_nodes=8)
        if len(sample_paths) < 3:
            sample_paths = self._fallback(career_name, grade)["sample_paths"]
        if not knowledge_map:
            knowledge_map = self._fallback(career_name, grade)["knowledge_map"]
        if not skills:
            skills = self._fallback(career_name, grade)["skills"]

        return {
            "description": description or self._fallback(career_name, grade)["description"],
            "skills": [str(item) for item in skills[:8]],
            "stories": stories[:10],
            "knowledge_map": knowledge_map[:8],
            "sample_paths": sample_paths[:3],
        }

    def _fallback(self, career_name: str, grade: str) -> Dict[str, Any]:
        stories = self._ensure_min_story_nodes(
            [
                {
                    "scene": "第一章：第一次任务",
                    "narration": f"你作为“小小{career_name}助理”接到第一个任务，需要在有限时间内做判断。",
                    "question": "你会如何开始？",
                    "choices": ["先观察问题细节再行动", "直接动手尝试", "先向老师或同伴请教"],
                    "feedback": [
                        "✅ 观察力+1：先看清问题，能减少失误。",
                        "🙂 行动力+1：勇于尝试很好，但下次可先评估风险。",
                        "✅ 沟通力+1：主动请教是高效学习方式。",
                    ],
                },
                {
                    "scene": "第二章：团队协作",
                    "narration": "你发现任务并不适合一个人完成，需要和同伴协同。",
                    "question": "你会怎么做？",
                    "choices": ["明确分工并约定时间", "自己全包避免麻烦", "等别人先做再跟着做"],
                    "feedback": [
                        "✅ 团队合作+1：分工清晰能提升效率。",
                        "⚠️ 责任感有，但团队任务更需要协作。",
                        "🙂 稳妥但被动，主动沟通会更好。",
                    ],
                },
                {
                    "scene": "第三章：成长复盘",
                    "narration": "任务完成后，你要总结这次体验，计划下一步成长。",
                    "question": "你会优先做什么？",
                    "choices": ["记录做得好和待改进点", "只庆祝成功不复盘", "把问题都归因于环境"],
                    "feedback": [
                        "✅ 反思力+1：复盘让你下一次更强。",
                        "🙂 成就感很重要，但复盘能让进步更快。",
                        "⚠️ 找客观原因有用，但也要看到自己可改进处。",
                    ],
                },
            ],
            career_name=career_name,
            min_nodes=8,
        )
        return {
            "description": f"{career_name}是一份需要热爱、学习和长期积累的职业。你现在在{grade}，已经可以开始打基础。",
            "skills": ["沟通表达", "逻辑思维", "持续学习", "团队合作"],
            "stories": stories,
            "knowledge_map": [
                {"subject": "语文", "link": "表达与理解能力是任何职业的基础", "grade_recommend": "当前就开始积累"},
                {"subject": "数学", "link": "逻辑与问题拆解能力来自数学训练", "grade_recommend": "每天稳定练习"},
                {"subject": "科学", "link": "科学素养帮助你理解真实世界与职业任务", "grade_recommend": "持续保持好奇心"},
            ],
            "sample_paths": [
                {"name": "🎓 大学（推荐）", "steps": ["初高中打牢基础学科", "根据兴趣选择相关专业", "大学期间参与实践项目"]},
                {"name": "💪 实践+进修", "steps": ["参加社团和校内实践", "利用线上课程补充技能", "继续深造获得更高能力"]},
                {"name": "🌟 跨界发展", "steps": ["主方向学习+副技能拓展", "跨学科项目训练", "形成个人特色发展路径"]},
            ],
        }

    def _ensure_min_story_nodes(self, stories: Any, career_name: str, min_nodes: int = 8) -> list:
        valid = []
        if isinstance(stories, list):
            for idx, node in enumerate(stories):
                if not isinstance(node, dict):
                    continue
                choices = node.get("choices") if isinstance(node.get("choices"), list) else []
                feedback = node.get("feedback") if isinstance(node.get("feedback"), list) else []
                if len(choices) < 3 or len(feedback) < 3:
                    continue
                valid.append(
                    {
                        "scene": str(node.get("scene", f"第{idx + 1}章：职业挑战")),
                        "narration": str(node.get("narration", f"你正在进行{career_name}体验任务。")),
                        "question": str(node.get("question", "你会怎么做？")),
                        "choices": [str(item) for item in choices[:3]],
                        "feedback": [str(item) for item in feedback[:3]],
                    }
                )
        templates = [
            ("职业观察", "你今天要先快速了解任务场景，做出第一个判断。", "面对陌生任务，你会先做什么？"),
            ("沟通协作", "你需要和同伴配合，才能让任务顺利推进。", "你会如何推动团队合作？"),
            ("问题定位", "任务遇到阻碍，需要你找出真正原因。", "你会优先采取哪一步？"),
            ("方案尝试", "你提出的方案要在有限资源下执行。", "你会如何安排执行顺序？"),
            ("风险处理", "出现了突发情况，需要冷静处理。", "你会先做什么？"),
            ("复盘改进", "任务结束后，要总结经验形成方法。", "你会怎样复盘？"),
            ("成长拓展", "你获得了新任务机会，需要提升能力。", "你会优先提升哪项能力？"),
            ("未来规划", "你要向老师展示下一阶段计划。", "你会怎么制定计划？"),
            ("社会责任", "你发现职业不仅是技能，也关乎责任。", "你会如何理解这份责任？"),
            ("终章展示", "你将分享这次职业体验收获。", "你会重点讲什么？"),
        ]
        while len(valid) < min_nodes:
            idx = len(valid)
            scene_name, narration, question = templates[idx % len(templates)]
            valid.append(
                {
                    "scene": f"第{idx + 1}章：{scene_name}",
                    "narration": f"{narration} 这次挑战与你的“{career_name}”梦想紧密相关。",
                    "question": question,
                    "choices": ["先观察并请教有经验的人", "马上执行自己想到的办法", "和同伴讨论后分工推进"],
                    "feedback": [
                        "✅ 观察力+1：先理解问题再行动，成功率更高。",
                        "🙂 行动力+1：勇于尝试很棒，记得同步风险评估。",
                        "✅ 协作力+1：分工合作能让复杂任务更高效。",
                    ],
                }
            )
        return valid
