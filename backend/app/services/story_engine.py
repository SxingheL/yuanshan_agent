from datetime import datetime, timezone
import json
import re
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from backend.app.db.models import CareerTemplate, Student, StudentDream, StudentHomeworkDetail
from backend.app.services.local_llm import LocalLLM


class StoryEngine:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.llm = LocalLLM()

    def get_next_node(self, dream_id: int, choice_idx: int) -> Dict[str, Any]:
        dream = self.db.query(StudentDream).filter(StudentDream.id == dream_id).first()
        if not dream:
            raise ValueError("梦想记录不存在")
        career = self.db.query(CareerTemplate).filter(CareerTemplate.id == dream.career_id).first()
        if not career:
            raise ValueError("职业模板不存在")
        stories = career.stories or []
        progress = list(dream.story_progress or [])
        current_step = len(progress)
        if current_step >= len(stories):
            path = self.generate_final_path(dream, career)
            return {
                "feedback": "故事已完成，已生成个性化路径。",
                "next_node": None,
                "is_end": True,
                "path_ready": True,
                "path": path,
                "reality_tip": f"{career.name}这条路需要长期学习与练习，不会一蹴而就。",
                "hope_tip": "虽然有挑战，但许多人就是一步步坚持走出来的。",
            }

        step = stories[current_step] if current_step < len(stories) else {}
        choices = step.get("choices", []) if isinstance(step, dict) else []
        feedbacks = step.get("feedback", []) if isinstance(step, dict) else []
        if not choices:
            path = self.generate_final_path(dream, career)
            return {
                "feedback": "故事节点异常，已直接为你生成路径。",
                "next_node": None,
                "is_end": True,
                "path_ready": True,
                "path": path,
                "reality_tip": f"{career.name}需要长期积累，请按路径稳步前进。",
                "hope_tip": "现在开始也不晚，每周前进一点点就很好。",
            }
        if choice_idx < 0 or choice_idx >= len(choices):
            raise ValueError("选项索引无效")

        selected_feedback = feedbacks[choice_idx] if choice_idx < len(feedbacks) else "✅ 你做出了认真思考后的选择。"
        earned_skill = self._extract_skill(selected_feedback)
        progress.append(
            {
                "step": current_step,
                "choice": choice_idx,
                "choice_text": choices[choice_idx],
                "feedback": selected_feedback,
                "earned_skill": earned_skill,
            }
        )
        dream.story_progress = progress
        skills = list(dream.earned_skills or [])
        if earned_skill:
            skills.append(earned_skill)
        dream.earned_skills = skills
        dream.updated_at = datetime.now(timezone.utc)
        self.db.commit()

        next_idx = current_step + 1
        next_node = stories[next_idx] if next_idx < len(stories) else None
        if next_node is None:
            self.generate_final_path(dream, career)
        return {
            "feedback": selected_feedback,
            "next_node": next_node,
            "is_end": next_node is None,
            "reality_tip": f"现实提示：{career.name}这条路并不轻松，需要持续学习和实践。",
            "hope_tip": "希望提示：难，但有人走过。你也可以通过每天的小进步接近它。",
        }

    def generate_final_path(self, dream: StudentDream, career: CareerTemplate) -> Dict[str, Any]:
        if dream.generated_path:
            return dream.generated_path

        student = self.db.query(Student).filter(Student.id == dream.student_id).first()
        scores = self._get_recent_scores(dream.student_id)
        earned_skills = [item for item in (dream.earned_skills or []) if isinstance(item, str)]

        prompt = f"""
为山村学生规划实现“{career.name}”梦想的个性化路径。必须输出JSON：
{{
  "knowledge_map":[
    {{"subject":"学科","link":"关联说明","grade_recommend":"阶段建议"}}
  ],
  "weekly_tasks":[
    {{"text":"具体任务","reason":"鼓励理由"}}
  ],
  "paths":[
    {{"name":"🎓 大学（推荐）","steps":["步骤1","步骤2","步骤3"]}},
    {{"name":"💪 实践+进修","steps":["步骤1","步骤2","步骤3"]}},
    {{"name":"🌟 跨界发展","steps":["步骤1","步骤2","步骤3"]}}
  ]
}}
输入信息：
- 学生年级：{student.grade if student else '未知'}
- 最近成绩：{scores}
- 在模拟中展现的能力：{", ".join(earned_skills) if earned_skills else "暂无"}
- 职业基础数据：{json.dumps(career.knowledge_map or [], ensure_ascii=False)}
强约束：
1. 禁止建议“辍学打工”；强调继续教育、在线学习、奖学金与可负担路径。
2. 步骤必须可操作、贴合农村学习条件。
3. weekly_tasks 给3到5条。
""".strip()
        fallback = self._fallback_path(career.name, student.grade if student else "", career)
        raw = self.llm.generate(prompt, fallback_answer=json.dumps(fallback, ensure_ascii=False))
        parsed = self._parse_json(raw)
        path_data = self._sanitize_path(parsed if parsed else fallback)

        dream.generated_path = path_data
        dream.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        return path_data

    def _get_recent_scores(self, student_id: str) -> List[float]:
        rows = (
            self.db.query(StudentHomeworkDetail.score)
            .filter(StudentHomeworkDetail.student_id == student_id)
            .order_by(StudentHomeworkDetail.created_at.desc())
            .limit(5)
            .all()
        )
        values = [float(row[0]) for row in rows if row and row[0] is not None]
        values.reverse()
        return values

    def _extract_skill(self, feedback: str) -> str:
        m = re.search(r"([\u4e00-\u9fa5A-Za-z]{2,12})\+1", feedback or "")
        if m:
            return m.group(1)
        return ""

    def _parse_json(self, raw: str) -> Dict[str, Any]:
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

    def _sanitize_path(self, data: Dict[str, Any]) -> Dict[str, Any]:
        knowledge_map = data.get("knowledge_map") if isinstance(data.get("knowledge_map"), list) else []
        weekly_tasks = data.get("weekly_tasks") if isinstance(data.get("weekly_tasks"), list) else []
        paths = data.get("paths") if isinstance(data.get("paths"), list) else []

        if len(weekly_tasks) < 3:
            weekly_tasks = [
                {"text": "每天完成当日作业后复盘1个知识点", "reason": "稳定学习习惯是实现梦想的长期引擎"},
                {"text": "每周阅读1篇与梦想职业相关的科普文章", "reason": "持续积累职业认知，保持兴趣"},
                {"text": "向老师或家长分享一次本周学习收获", "reason": "表达与反馈会让学习更有效"},
            ]
        if len(paths) < 3:
            paths = [
                {"name": "🎓 大学（推荐）", "steps": ["初高中打牢基础学科", "选择相关本科专业并争取奖助学金", "大学阶段参与实践项目"]},
                {"name": "💪 实践+进修", "steps": ["利用校内社团或县城资源做实践", "持续完成线上课程", "逐步取得更高层次证书"]},
                {"name": "🌟 跨界发展", "steps": ["主学科稳定推进", "培养一个交叉技能", "通过项目形成个人特色方向"]},
            ]

        sanitized_paths = []
        for path in paths[:3]:
            name = str(path.get("name", "") or "")
            steps = path.get("steps") if isinstance(path.get("steps"), list) else []
            cleaned_steps = []
            for step in steps[:6]:
                text = str(step).replace("辍学", "持续学习")
                if "打工" in text and "学习" not in text and "进修" not in text:
                    text = "先完成当前学段学习，再结合实践逐步提升职业能力"
                cleaned_steps.append(text)
            sanitized_paths.append({"name": name or "成长路径", "steps": cleaned_steps})

        return {
            "knowledge_map": knowledge_map[:8],
            "weekly_tasks": weekly_tasks[:5],
            "paths": sanitized_paths,
        }

    def _fallback_path(self, career_name: str, grade: str, career: CareerTemplate) -> Dict[str, Any]:
        knowledge_map = career.knowledge_map if isinstance(career.knowledge_map, list) else []
        if not knowledge_map:
            knowledge_map = [
                {"subject": "语文", "link": f"成为{career_name}需要清晰表达与理解能力", "grade_recommend": "当前阶段持续阅读与表达"},
                {"subject": "数学", "link": "数学训练逻辑思维和问题分析能力", "grade_recommend": "每天稳定练习"},
                {"subject": "科学", "link": "科学素养帮助理解职业背后的原理", "grade_recommend": "结合课堂和生活观察"},
            ]
        return {
            "knowledge_map": knowledge_map,
            "weekly_tasks": [
                {"text": "每天完成课堂作业后，额外做1道思考题", "reason": "提升独立思考能力"},
                {"text": "每周一次和老师讨论职业相关问题", "reason": "及时获得反馈，方向更清晰"},
                {"text": "周末观看1个免费公开课或科普视频并做笔记", "reason": "利用低成本资源拓展认知"},
            ],
            "paths": [
                {"name": "🎓 大学（推荐）", "steps": [f"{grade or '当前'}阶段打牢基础", "高中选择相关学科方向", "报考相关本科专业并争取奖助学金"]},
                {"name": "💪 实践+进修", "steps": ["参加校内外实践活动", "完成线上技能课程", "持续进修形成专业能力"]},
                {"name": "🌟 跨界发展", "steps": ["主方向学习+副方向探索", "参与跨学科项目", "逐步形成复合型竞争力"]},
            ],
        }
