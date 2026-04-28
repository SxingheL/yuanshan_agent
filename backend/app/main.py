from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.auth import hash_password
from backend.app.config import settings
from backend.app.db.database import Base, SessionLocal, engine
from backend.app.db.models import (
    Analogy,
    BadgeDefinition,
    CareerTemplate,
    DialectMap,
    KnowledgePoint,
    MasterLesson,
    QuestionBank,
    Student,
    StudentAbility,
    StudentFlashMoment,
    StudentGoal,
    StudentSemesterStats,
    TeacherTodo,
    User,
)
from backend.app.routes.auth import router as auth_router
from backend.app.routes.communication import router as communication_router
from backend.app.routes.dream import router as dream_router
from backend.app.routes.homework import router as homework_router
from backend.app.routes.knowledge import router as knowledge_router
from backend.app.routes.legacy_agents import router as legacy_agents_router
from backend.app.routes.lesson_plan import router as lesson_plan_router
from backend.app.routes.microcourse import router as microcourse_router
from backend.app.routes.psychology import router as psychology_router
from backend.app.routes.student_archive import router as student_archive_router
from backend.app.routes.teacher_dashboard import router as teacher_dashboard_router
from backend.app.routes.teacher_growth import router as teacher_growth_router
from backend.app.services.psychology_scheduler import start_psychology_scheduler
from backend.app.services.student_archive_scheduler import start_student_archive_scheduler


app = FastAPI(title=settings.app_title)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def seed_demo_users() -> None:
    demo_users = [
        {
            "username": "teacher001",
            "password": "123456",
            "role": "teacher",
            "school_id": "school-qingshan",
            "school_name": "青山村小学",
            "full_name": "李芳老师",
        },
        {
            "username": "student001",
            "password": "123456",
            "role": "student",
            "school_id": "school-qingshan",
            "school_name": "青山村小学",
            "full_name": "王小明",
        },
    ]

    def is_supported_password_hash(value: object) -> bool:
        if not isinstance(value, str) or not value:
            return False
        return value.startswith("$2") or value.startswith("pbkdf2_sha256$")

    db = SessionLocal()
    try:
        for item in demo_users:
            existed = db.query(User).filter(User.username == item["username"]).first()
            if existed:
                if not is_supported_password_hash(existed.password_hash):
                    existed.password_hash = hash_password(item["password"])
                existed.role = item["role"]
                existed.school_id = item["school_id"]
                existed.school_name = item["school_name"]
                existed.full_name = item["full_name"]
                continue
            db.add(
                User(
                    username=item["username"],
                    password_hash=hash_password(item["password"]),
                    role=item["role"],
                    school_id=item["school_id"],
                    school_name=item["school_name"],
                    full_name=item["full_name"],
                )
            )
        db.commit()
    finally:
        db.close()


def seed_demo_students_and_questions() -> None:
    demo_students = [
        {"id": "S001", "name": "王小明", "class_id": "class_5", "grade": "五年级", "family_type": "留守"},
        {"id": "S002", "name": "李小花", "class_id": "class_5", "grade": "五年级", "family_type": "普通"},
        {"id": "S003", "name": "张大山", "class_id": "class_5", "grade": "五年级", "family_type": "困难"},
        {"id": "S004", "name": "刘梅梅", "class_id": "class_5", "grade": "五年级", "family_type": "留守"},
        {"id": "S005", "name": "赵小龙", "class_id": "class_5", "grade": "五年级", "family_type": "单亲"},
    ]
    demo_questions = [
        {
            "class_id": "class_5",
            "subject": "mathematics",
            "sequence_no": 1,
            "question_text": "28 + 17 = ?",
            "standard_answer": "45",
            "knowledge_point": "进位加法",
        },
        {
            "class_id": "class_5",
            "subject": "mathematics",
            "sequence_no": 2,
            "question_text": "84 - 29 = ?",
            "standard_answer": "55",
            "knowledge_point": "退位减法",
        },
        {
            "class_id": "class_5",
            "subject": "mathematics",
            "sequence_no": 3,
            "question_text": "3/4 ÷ 1/2 = ?",
            "standard_answer": "1.5",
            "knowledge_point": "分数除法",
        },
        {
            "class_id": "class_5",
            "subject": "mathematics",
            "sequence_no": 4,
            "question_text": "一个长方形长6宽4，面积是多少？",
            "standard_answer": "24",
            "knowledge_point": "面积计算",
        },
        {
            "class_id": "class_5",
            "subject": "chinese",
            "sequence_no": 1,
            "question_text": "《燕子》一文描写了什么季节？",
            "standard_answer": "春天",
            "knowledge_point": "内容理解",
        },
        {
            "class_id": "class_5",
            "subject": "chinese",
            "sequence_no": 2,
            "question_text": "写出文中描写燕子外形的一个词。",
            "standard_answer": "俊俏",
            "knowledge_point": "词语积累",
        },
        {
            "class_id": "class_5",
            "subject": "chinese",
            "sequence_no": 3,
            "question_text": "作者为什么喜欢燕子？",
            "standard_answer": "因为燕子活泼可爱",
            "knowledge_point": "表达感悟",
        },
    ]

    db = SessionLocal()
    try:
        for item in demo_students:
            existed = db.query(Student).filter(Student.id == item["id"]).first()
            if existed:
                continue
            db.add(
                Student(
                    id=item["id"],
                    name=item["name"],
                    class_id=item["class_id"],
                    grade=item["grade"],
                    family_type=item["family_type"],
                    growth_archive={},
                )
            )

        for item in demo_questions:
            existed = (
                db.query(QuestionBank)
                .filter(
                    QuestionBank.class_id == item["class_id"],
                    QuestionBank.subject == item["subject"],
                    QuestionBank.sequence_no == item["sequence_no"],
                )
                .first()
            )
            if existed:
                continue
            db.add(
                QuestionBank(
                    class_id=item["class_id"],
                    subject=item["subject"],
                    sequence_no=item["sequence_no"],
                    question_text=item["question_text"],
                    standard_answer=item["standard_answer"],
                    knowledge_point=item["knowledge_point"],
                )
            )
        db.commit()
    finally:
        db.close()


def seed_demo_knowledge() -> None:
    knowledge_points = [
        {
            "subject": "数学",
            "grade": "五年级",
            "name": "分数除法",
            "content": "分数除法可以理解成：把一个分数表示的数量，再按某个标准继续平均分。",
            "example": "3/4 ÷ 1/2，表示3/4里面有几个1/2，结果是1.5。",
        },
        {
            "subject": "数学",
            "grade": "三年级",
            "name": "进位加法",
            "content": "个位相加满十，就要向前一位进1，再继续计算。",
            "example": "28 + 17，先算8+7=15，写5进1，再算2+1+1=4，结果45。",
        },
        {
            "subject": "数学",
            "grade": "三年级",
            "name": "长方形面积",
            "content": "长方形面积等于长乘宽，表示这个图形一共占了多少格地方。",
            "example": "长6宽4，面积就是6×4=24。",
        },
        {
            "subject": "语文",
            "grade": "五年级",
            "name": "内容理解",
            "content": "内容理解要抓住文章写了什么、为什么这样写、表达了什么感情。",
            "example": "读《燕子》时，可以先找季节、景物和作者的情感。",
        },
        {
            "subject": "科学",
            "grade": "四年级",
            "name": "蒸发",
            "content": "蒸发是液体表面的水慢慢变成看不见的水蒸气跑到空气里。",
            "example": "湿衣服晒在太阳下，过一会儿就干了，这就是蒸发。",
        },
    ]
    analogy_rows = {
        "分数除法": [
            ("农村", "分数除法就像把三块四分之三亩的地，再按半亩一份去分，看一共能分出几份。"),
            ("分馍", "就像家里还剩下四分之三张馍，现在每半张算一份，看还能分成几份。"),
        ],
        "进位加法": [
            ("赶集", "进位加法像赶集凑钱，个位的钱凑满十元，就先换成一张十元票送到前一位。"),
        ],
        "长方形面积": [
            ("种地", "长方形面积像量一块菜地有多大，长边走几步、宽边走几步，长乘宽就是总面积。"),
        ],
        "内容理解": [
            ("农村", "理解课文就像听老人讲故事，不光要知道讲了什么，还要听出他为什么这样讲。"),
        ],
        "蒸发": [
            ("做饭", "蒸发像锅里的水慢慢冒热气，水没有不见，而是变成看不见的小水汽跑到空中。"),
        ],
    }
    dialect_rows = {
        "咋子": "怎么",
        "啥子": "什么",
        "娃儿": "孩子",
        "整": "做",
        "莫得": "没有",
    }

    db = SessionLocal()
    try:
        point_id_map = {}
        for item in knowledge_points:
            existed = (
                db.query(KnowledgePoint)
                .filter(
                    KnowledgePoint.subject == item["subject"],
                    KnowledgePoint.grade == item["grade"],
                    KnowledgePoint.name == item["name"],
                )
                .first()
            )
            if not existed:
                existed = KnowledgePoint(**item)
                db.add(existed)
                db.flush()
            point_id_map[item["name"]] = existed.id

        for point_name, analogies in analogy_rows.items():
            point_id = point_id_map.get(point_name)
            if not point_id:
                continue
            for scenario, analogy_text in analogies:
                existed = (
                    db.query(Analogy)
                    .filter(
                        Analogy.knowledge_point_id == point_id,
                        Analogy.scenario == scenario,
                        Analogy.analogy_text == analogy_text,
                    )
                    .first()
                )
                if not existed:
                    db.add(
                        Analogy(
                            knowledge_point_id=point_id,
                            scenario=scenario,
                            analogy_text=analogy_text,
                        )
                    )

        for dialect_word, mandarin_word in dialect_rows.items():
            existed = (
                db.query(DialectMap)
                .filter(DialectMap.dialect_word == dialect_word)
                .first()
            )
            if not existed:
                db.add(
                    DialectMap(
                        dialect_word=dialect_word,
                        mandarin_word=mandarin_word,
                    )
                )
        db.commit()
    finally:
        db.close()


def seed_demo_master_lessons() -> None:
    rows = [
        {
            "subject": "数学",
            "grade": "五年级",
            "topic": "认识分数",
            "title": "特级教师张老师《认识分数》",
            "url": "https://www.bilibili.com/video/BV1x54y1p7fA",
            "description": "用生活化切入讲解分数概念，结构清晰。",
            "transcript_text": "同学们先看这个苹果，怎么把一个苹果平均分给两个人？这就是二分之一...",
        },
        {
            "subject": "语文",
            "grade": "五年级",
            "topic": "燕子",
            "title": "名师公开课《燕子》教学实录",
            "url": "https://www.bilibili.com/video/BV1mK4y1Y7cD",
            "description": "关注朗读节奏与情感体验。",
            "transcript_text": "先闭上眼听一段春天的声音，再带着想象朗读课文...",
        },
        {
            "subject": "数学",
            "grade": "六年级",
            "topic": "比例",
            "title": "全国优质课《比例的意义》",
            "url": "https://www.bilibili.com/video/BV1mb411W7Q2",
            "description": "强调探究式提问和板书结构。",
            "transcript_text": "请大家观察这两组数据，哪一组更像同比变化？为什么？",
        },
    ]
    db = SessionLocal()
    try:
        for item in rows:
            existed = (
                db.query(MasterLesson)
                .filter(
                    MasterLesson.subject == item["subject"],
                    MasterLesson.grade == item["grade"],
                    MasterLesson.topic == item["topic"],
                    MasterLesson.title == item["title"],
                )
                .first()
            )
            if existed:
                continue
            db.add(MasterLesson(**item, embedding=[]))
        db.commit()
    finally:
        db.close()


def seed_badge_definitions() -> None:
    rows = [
        {
            "id": "lesson_master",
            "name": "连续30天备课达人",
            "description": "连续30天完成备课记录",
            "icon_emoji": "🌟",
            "condition_type": "lesson_plan_count",
            "condition_threshold": 30,
        },
        {
            "id": "micro_pioneer",
            "name": "微课达人",
            "description": "完成20次微课分析",
            "icon_emoji": "🎬",
            "condition_type": "micro_analysis_count",
            "condition_threshold": 20,
        },
        {
            "id": "visit_enthusiast",
            "name": "家校沟通能手",
            "description": "累计30次家访记录",
            "icon_emoji": "💬",
            "condition_type": "visit_record_count",
            "condition_threshold": 30,
        },
        {
            "id": "homework_master",
            "name": "作业批改行家",
            "description": "完成50次作业批改",
            "icon_emoji": "📝",
            "condition_type": "homework_batch_count",
            "condition_threshold": 50,
        },
        {
            "id": "forum_star",
            "name": "互助之星",
            "description": "论坛发帖/回复超过20次",
            "icon_emoji": "🤝",
            "condition_type": "forum_post_count",
            "condition_threshold": 20,
        },
        {
            "id": "all_rounder",
            "name": "全能教师",
            "description": "五维平均分≥85",
            "icon_emoji": "🏆",
            "condition_type": "five_dimension_avg",
            "condition_threshold": 85,
        },
    ]
    db = SessionLocal()
    try:
        for item in rows:
            existed = db.query(BadgeDefinition).filter(BadgeDefinition.id == item["id"]).first()
            if existed:
                existed.name = item["name"]
                existed.description = item["description"]
                existed.icon_emoji = item["icon_emoji"]
                existed.condition_type = item["condition_type"]
                existed.condition_threshold = item["condition_threshold"]
                existed.is_active = True
                continue
            db.add(BadgeDefinition(**item))
        db.commit()
    finally:
        db.close()


def seed_dream_careers() -> None:
    rows = [
        {
            "name": "宇航员",
            "icon": "🚀",
            "color": "#E8F4FC",
            "description": "探索太空、执行航天任务，需要扎实学科基础与团队协作能力。",
            "skills": ["逻辑思维", "英语沟通", "科学素养", "抗压能力"],
            "stories": [
                {
                    "scene": "第一章：发射前检查",
                    "narration": "你是航天任务见习助理，发射前发现一个参数异常。",
                    "question": "你会怎么做？",
                    "choices": ["立刻上报并复核", "先自己改掉再说", "先忽略，等别人发现"],
                    "feedback": [
                        "✅ 责任感+1：关键任务必须先保证安全。",
                        "⚠️ 行动力+1：积极但需遵循规范流程。",
                        "❌ 安全意识需要提升：细节可能影响任务成败。",
                    ],
                },
                {
                    "scene": "第二章：太空沟通",
                    "narration": "地面传来英文指令，需要快速准确传达。",
                    "question": "你如何处理？",
                    "choices": ["确认关键词后准确复述", "大概猜测意思", "请同伴协同确认后再执行"],
                    "feedback": [
                        "✅ 英语能力+1：准确表达避免操作风险。",
                        "⚠️ 勇气可嘉，但航天任务不能靠猜。",
                        "✅ 团队合作+1：关键场景下协作是高质量决策。",
                    ],
                },
                {
                    "scene": "第三章：任务复盘",
                    "narration": "任务结束后，你需要总结成长计划。",
                    "question": "你会优先做什么？",
                    "choices": ["记录收获与不足，制定学习计划", "只庆祝成功", "把问题归因于运气"],
                    "feedback": [
                        "✅ 反思力+1：复盘让你进步更快。",
                        "🙂 成就感很重要，复盘会让下次更稳。",
                        "⚠️ 客观分析很重要，避免简单归因。",
                    ],
                },
            ],
            "knowledge_map": [
                {"subject": "数学", "link": "轨道和参数计算依赖数学基础", "grade_recommend": "当前阶段巩固计算与应用题"},
                {"subject": "物理", "link": "力学与能量知识支撑航天理解", "grade_recommend": "中学阶段重点学习"},
                {"subject": "英语", "link": "国际协作任务常需英文沟通", "grade_recommend": "从词汇和表达持续积累"},
            ],
            "sample_paths": [
                {"name": "🎓 大学（推荐）", "steps": ["高中强化数理基础", "报考航空航天相关本科", "大学参与航天实践项目"]},
                {"name": "💪 实践+进修", "steps": ["参加科技社团和竞赛", "通过线上课程提升", "持续进修相关专业"]},
                {"name": "🌟 跨界发展", "steps": ["主修工科方向", "叠加计算机能力", "进入航天数据与软件方向"]},
            ],
        },
        {
            "name": "乡村兽医",
            "icon": "🐮",
            "color": "#E8F9EC",
            "description": "守护乡村动物健康，连接养殖与科学管理，是乡村振兴的重要职业。",
            "skills": ["观察判断", "沟通表达", "生物基础", "责任意识"],
            "stories": [
                {
                    "scene": "第一章：首次出诊",
                    "narration": "你跟随师傅到村里看一头生病的牛。",
                    "question": "你先做什么？",
                    "choices": ["先观察状态并询问喂养情况", "直接上手处理", "让家长决定怎么办"],
                    "feedback": [
                        "✅ 观察力+1：先收集信息再判断更科学。",
                        "⚠️ 行动积极，但先评估风险更安全。",
                        "🙂 尊重家长很重要，也要发挥专业判断。",
                    ],
                },
                {
                    "scene": "第二章：临时情况",
                    "narration": "治疗工具不齐全，动物状态在变化。",
                    "question": "你怎么处理？",
                    "choices": ["联系师傅远程指导", "先做安全的基础处置", "暂时离开等明天再说"],
                    "feedback": [
                        "✅ 求助能力+1：关键时刻及时沟通很专业。",
                        "✅ 应变力+1：先做安全处置可争取时间。",
                        "⚠️ 需提升时效意识，拖延可能加重问题。",
                    ],
                },
                {
                    "scene": "第三章：健康宣教",
                    "narration": "村民希望你给出长期预防建议。",
                    "question": "你会怎么做？",
                    "choices": ["给出喂养和卫生清单", "只说按经验来", "让村民自己摸索"],
                    "feedback": [
                        "✅ 服务意识+1：预防比治疗更有价值。",
                        "🙂 经验有用，结构化建议更实用。",
                        "⚠️ 可再主动一些，帮助村民建立方法。",
                    ],
                },
            ],
            "knowledge_map": [
                {"subject": "科学", "link": "动物身体与疾病基础来自科学学习", "grade_recommend": "当前重视观察实验"},
                {"subject": "语文", "link": "和村民沟通、记录病例都要清晰表达", "grade_recommend": "加强口头和书面表达"},
                {"subject": "数学", "link": "药量和成本都需要准确计算", "grade_recommend": "持续训练计算准确率"},
            ],
            "sample_paths": [
                {"name": "🎓 大学（推荐）", "steps": ["中学打牢科学基础", "报考动物医学/畜牧兽医专业", "返乡服务或继续深造"]},
                {"name": "💪 实践+进修", "steps": ["参与校内外养殖实践", "系统学习在线兽医课程", "通过职业培训提升资格"]},
                {"name": "🌟 跨界发展", "steps": ["学习兽医基础", "叠加养殖管理与电商知识", "发展现代农业服务能力"]},
            ],
        },
    ]
    db = SessionLocal()
    try:
        for item in rows:
            existed = (
                db.query(CareerTemplate)
                .filter(
                    CareerTemplate.name == item["name"],
                    CareerTemplate.is_custom.is_(False),
                )
                .first()
            )
            if existed:
                existed.icon = item["icon"]
                existed.color = item["color"]
                existed.description = item["description"]
                existed.skills = item["skills"]
                existed.stories = item["stories"]
                existed.knowledge_map = item["knowledge_map"]
                existed.sample_paths = item["sample_paths"]
                continue
            db.add(
                CareerTemplate(
                    name=item["name"],
                    icon=item["icon"],
                    color=item["color"],
                    description=item["description"],
                    skills=item["skills"],
                    stories=item["stories"],
                    knowledge_map=item["knowledge_map"],
                    sample_paths=item["sample_paths"],
                    is_custom=False,
                    created_by=None,
                )
            )
        db.commit()
    finally:
        db.close()


def seed_student_archive_demo() -> None:
    db = SessionLocal()
    try:
        student = db.query(Student).filter(Student.id == "S001").first()
        teacher = db.query(User).filter(User.username == "teacher001").first()
        if not student or not teacher:
            return

        if not db.query(StudentAbility).filter(StudentAbility.student_id == "S001").first():
            db.add_all(
                [
                    StudentAbility(
                        student_id="S001",
                        ability_name="科学探索",
                        description="对天文和自然科学表现出浓厚兴趣",
                        source="teacher",
                    ),
                    StudentAbility(
                        student_id="S001",
                        ability_name="绘画创作",
                        description="参加学校绘画比赛获三等奖",
                        source="teacher",
                    ),
                ]
            )

        if not db.query(StudentFlashMoment).filter(StudentFlashMoment.student_id == "S001").first():
            db.add_all(
                [
                    StudentFlashMoment(
                        student_id="S001",
                        teacher_id=teacher.id,
                        original_text="今天王小明第一次举手回答问题，虽然答错了，但是有勇气",
                        polished_text="第一次举手回答应用题，虽然方法不完全正确，但勇气可嘉！",
                        encouragement="勇敢尝试就是成功的开始，老师为你骄傲！",
                        moment_date=datetime(2025, 4, 15).date(),
                        is_public=True,
                    ),
                    StudentFlashMoment(
                        student_id="S001",
                        teacher_id=teacher.id,
                        original_text="王小明主动帮助新同学认识班级",
                        polished_text="主动带新同学融入班级，展现了温暖和责任感。",
                        encouragement="你愿意帮助他人，这份善意很珍贵！",
                        moment_date=datetime(2025, 3, 10).date(),
                        is_public=True,
                    ),
                ]
            )

        if not db.query(StudentGoal).filter(StudentGoal.student_id == "S001").first():
            db.add_all(
                [
                    StudentGoal(
                        student_id="S001",
                        title="数学：攻克分数运算",
                        description="期末分数单元测试达到80分以上",
                        target_progress=100,
                        current_progress=68,
                        due_date=datetime(2025, 7, 1).date(),
                        is_completed=False,
                        generated_by="ai",
                    ),
                    StudentGoal(
                        student_id="S001",
                        title="阅读：每月完成一本课外书",
                        description="本学期累计完成8本课外阅读",
                        target_progress=100,
                        current_progress=75,
                        due_date=datetime(2025, 7, 10).date(),
                        is_completed=False,
                        generated_by="teacher",
                    ),
                ]
            )

        stats = db.query(StudentSemesterStats).filter(StudentSemesterStats.student_id == "S001").first()
        if not stats:
            db.add(
                StudentSemesterStats(
                    student_id="S001",
                    semester="2024-2025",
                    avg_score=82.5,
                    attendance_rate=96.0,
                    flash_count=2,
                    dream="宇航员",
                )
            )
        db.commit()
    finally:
        db.close()


def seed_teacher_todos() -> None:
    db = SessionLocal()
    try:
        teacher = db.query(User).filter(User.username == "teacher001").first()
        if not teacher:
            return
        today = datetime.now().date()
        rows = [
            ("备三年级语文第8课《燕子》", 2, False),
            ("批改五年级数学作业", 1, True),
            ("联系王小花家长了解近况", 1, False),
        ]
        for content, priority, completed in rows:
            existed = (
                db.query(TeacherTodo)
                .filter(
                    TeacherTodo.teacher_id == teacher.id,
                    TeacherTodo.target_date == today,
                    TeacherTodo.content == content,
                )
                .first()
            )
            if existed:
                continue
            db.add(
                TeacherTodo(
                    teacher_id=teacher.id,
                    content=content,
                    target_date=today,
                    is_completed=completed,
                    priority=priority,
                )
            )
        db.commit()
    finally:
        db.close()


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    seed_demo_users()
    seed_demo_students_and_questions()
    seed_demo_knowledge()
    seed_demo_master_lessons()
    seed_badge_definitions()
    seed_dream_careers()
    seed_student_archive_demo()
    seed_teacher_todos()
    start_psychology_scheduler()
    start_student_archive_scheduler()


@app.get("/api/health")
def healthcheck() -> dict:
    return {"status": "ok", "service": settings.app_title}


app.include_router(auth_router)
app.include_router(lesson_plan_router)
app.include_router(homework_router)
app.include_router(knowledge_router)
app.include_router(communication_router)
app.include_router(microcourse_router)
app.include_router(legacy_agents_router)
app.include_router(teacher_growth_router)
app.include_router(psychology_router)
app.include_router(dream_router)
app.include_router(student_archive_router)
app.include_router(teacher_dashboard_router)
