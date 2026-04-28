from datetime import datetime, timezone

from sqlalchemy import Boolean, JSON, Column, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint

from backend.app.db.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(32), index=True, nullable=False)
    school_id = Column(String(64), default="default-school")
    school_name = Column(String(128), default="青山村小学")
    full_name = Column(String(64), default="")
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


class LessonPlanRecord(Base):
    __tablename__ = "lesson_plan_records"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(String(64), unique=True, index=True)
    teacher_id = Column(Integer, ForeignKey("users.id"), index=True)
    subject = Column(String(32), index=True)
    topic = Column(String(128), index=True)
    grade_config = Column(String(128), index=True)
    duration = Column(Integer)
    title = Column(String(255))
    plan_summary = Column(Text, default="")
    plan_json = Column(JSON)
    self_study_tasks = Column(JSON)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )


class Student(Base):
    __tablename__ = "students"

    id = Column(String(32), primary_key=True)
    name = Column(String(64), nullable=False, index=True)
    class_id = Column(String(32), nullable=False, index=True)
    grade = Column(String(32), nullable=False)
    guardian_name = Column(String(64), default="")
    contact = Column(String(32), default="")
    family_type = Column(String(32), default="")
    ethnicity = Column(String(32), default="")
    health_status = Column(String(64), default="")
    growth_archive = Column(JSON, default=dict)
    last_homework_submit = Column(Date, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


class HomeworkRecord(Base):
    __tablename__ = "homework_records"

    id = Column(Integer, primary_key=True, index=True)
    homework_id = Column(String(64), unique=True, index=True)
    class_id = Column(String(32), index=True)
    subject = Column(String(32), index=True)
    date = Column(Date, index=True)
    total_students = Column(Integer, default=0)
    submitted_count = Column(Integer, default=0)
    summary_stats = Column(JSON, default=dict)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


class StudentHomeworkDetail(Base):
    __tablename__ = "student_homework_details"

    id = Column(Integer, primary_key=True, index=True)
    homework_id = Column(String(64), ForeignKey("homework_records.homework_id"), index=True)
    student_id = Column(String(32), ForeignKey("students.id"), index=True)
    score = Column(Float, default=0)
    completion_rate = Column(Float, default=0)
    wrong_knowledge_points = Column(JSON, default=list)
    answers = Column(JSON, default=list)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


class KnowledgeMasteryHistory(Base):
    __tablename__ = "knowledge_mastery_history"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(String(32), ForeignKey("students.id"), index=True)
    knowledge_point = Column(String(64), index=True)
    homework_date = Column(Date, index=True)
    is_correct = Column(Boolean, default=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


class QuestionBank(Base):
    __tablename__ = "question_bank"

    id = Column(Integer, primary_key=True, index=True)
    class_id = Column(String(32), index=True)
    subject = Column(String(32), index=True)
    sequence_no = Column(Integer, nullable=False)
    question_text = Column(Text, nullable=False)
    standard_answer = Column(String(128), nullable=False)
    knowledge_point = Column(String(64), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


class KnowledgePoint(Base):
    __tablename__ = "knowledge_points"

    id = Column(Integer, primary_key=True, index=True)
    subject = Column(String(32), index=True)
    grade = Column(String(32), index=True)
    name = Column(String(64), index=True)
    content = Column(Text, nullable=False)
    example = Column(Text, default="")
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


class Analogy(Base):
    __tablename__ = "analogies"

    id = Column(Integer, primary_key=True, index=True)
    knowledge_point_id = Column(Integer, ForeignKey("knowledge_points.id"), index=True)
    scenario = Column(String(64), index=True)
    analogy_text = Column(Text, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


class DialectMap(Base):
    __tablename__ = "dialect_map"

    id = Column(Integer, primary_key=True, index=True)
    dialect_word = Column(String(64), index=True)
    mandarin_word = Column(String(64), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


class VisitRecord(Base):
    __tablename__ = "visit_records"

    id = Column(Integer, primary_key=True, index=True)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    student_id = Column(String(32), ForeignKey("students.id"), nullable=False, index=True)
    visit_date = Column(Date, nullable=False, index=True)
    content = Column(Text, default="")
    notes = Column(Text, default="")
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class MasterLesson(Base):
    __tablename__ = "master_lessons"

    id = Column(Integer, primary_key=True, index=True)
    subject = Column(String(32), nullable=False, index=True)
    grade = Column(String(20), nullable=False, index=True)
    topic = Column(String(128), nullable=False, index=True)
    title = Column(String(256), nullable=False)
    url = Column(String(512), nullable=False)
    description = Column(Text, default="")
    transcript_text = Column(Text, default="")
    embedding = Column(JSON, default=list)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


class MicrocourseAnalysis(Base):
    __tablename__ = "microcourse_analysis"

    id = Column(Integer, primary_key=True, index=True)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    subject = Column(String(32), default="", index=True)
    grade = Column(String(20), default="", index=True)
    topic = Column(String(128), default="", index=True)
    scores = Column(JSON, default=dict)
    summary = Column(Text, default="")
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )


class NoticeRecord(Base):
    __tablename__ = "notice_records"

    id = Column(Integer, primary_key=True, index=True)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    draft = Column(Text, default="")
    short_version = Column(Text, default="")
    rich_version = Column(Text, default="")
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )


class ForumPost(Base):
    __tablename__ = "forum_posts"

    id = Column(Integer, primary_key=True, index=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(255), default="")
    content = Column(Text, default="")
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )


class TeacherStats(Base):
    __tablename__ = "teacher_stats"

    teacher_id = Column(Integer, ForeignKey("users.id"), primary_key=True, index=True)
    total_lesson_plans = Column(Integer, default=0)
    total_micro_analysis = Column(Integer, default=0)
    total_visit_records = Column(Integer, default=0)
    total_homework_batches = Column(Integer, default=0)
    total_forum_posts = Column(Integer, default=0)
    five_dimensions = Column(JSON, default=dict)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class TeacherBadge(Base):
    __tablename__ = "teacher_badges"
    __table_args__ = (UniqueConstraint("teacher_id", "badge_id", name="uq_teacher_badge"),)

    id = Column(Integer, primary_key=True, index=True)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    badge_id = Column(String(64), nullable=False, index=True)
    badge_name = Column(String(128), default="")
    earned_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )


class BadgeDefinition(Base):
    __tablename__ = "badge_definitions"

    id = Column(String(64), primary_key=True)
    name = Column(String(128), nullable=False)
    description = Column(Text, default="")
    icon_emoji = Column(String(16), default="🏅")
    condition_type = Column(String(32), nullable=False, index=True)
    condition_threshold = Column(Integer, nullable=False, default=1)
    is_active = Column(Boolean, default=True, index=True)


class PsychologyAnalysis(Base):
    __tablename__ = "psychology_analyses"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(String(32), ForeignKey("students.id"), nullable=False, index=True)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    analysis_date = Column(Date, nullable=False, index=True)
    materials = Column(JSON, default=dict)
    alert_level = Column(Integer, nullable=False, default=0)
    alert_reason = Column(Text, default="")
    action_suggestion = Column(Text, default="")
    today_reminder = Column(Text, default="")
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )


class StudentAlert(Base):
    __tablename__ = "student_alerts"
    __table_args__ = (UniqueConstraint("teacher_id", "student_id", name="uq_student_alert"),)

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(String(32), ForeignKey("students.id"), nullable=False, index=True)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    alert_level = Column(Integer, default=0, index=True)
    reason = Column(Text, default="")
    suggestion = Column(Text, default="")
    today_reminder = Column(Text, default="")
    last_analysis_date = Column(Date, nullable=True, index=True)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class CareList(Base):
    __tablename__ = "care_lists"

    id = Column(Integer, primary_key=True, index=True)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    student_id = Column(String(32), ForeignKey("students.id"), nullable=True, index=True)
    list_type = Column(String(10), nullable=False, index=True)  # today / week
    content = Column(Text, nullable=False)
    priority = Column(Integer, default=1, index=True)
    is_completed = Column(Boolean, default=False, index=True)
    due_date = Column(Date, nullable=True, index=True)
    source = Column(String(10), default="ai")  # ai or manual
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )


class TeacherTodo(Base):
    __tablename__ = "teacher_todos"

    id = Column(Integer, primary_key=True, index=True)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    target_date = Column(Date, nullable=False, index=True)
    is_completed = Column(Boolean, default=False, index=True)
    priority = Column(Integer, default=1, index=True)  # 1=普通,2=高优先
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class CareerTemplate(Base):
    __tablename__ = "career_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(64), nullable=False, index=True)
    icon = Column(String(16), default="✨")
    color = Column(String(32), default="#EDF6E0")
    description = Column(Text, default="")
    skills = Column(JSON, default=list)
    stories = Column(JSON, default=list)
    knowledge_map = Column(JSON, default=list)
    sample_paths = Column(JSON, default=list)
    is_custom = Column(Boolean, default=False, index=True)
    created_by = Column(String(32), nullable=True, index=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )


class StudentDream(Base):
    __tablename__ = "student_dreams"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(String(32), ForeignKey("students.id"), nullable=False, index=True)
    career_id = Column(Integer, ForeignKey("career_templates.id"), nullable=False, index=True)
    custom_career_name = Column(String(128), default="")
    story_progress = Column(JSON, default=list)
    earned_skills = Column(JSON, default=list)
    generated_path = Column(JSON, default=dict)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        index=True,
    )


class StudentFlashMoment(Base):
    __tablename__ = "student_flash_moments"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(String(32), ForeignKey("students.id"), nullable=False, index=True)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    original_text = Column(Text, nullable=False)
    polished_text = Column(Text, default="")
    encouragement = Column(Text, default="")
    moment_date = Column(Date, nullable=False, index=True)
    is_public = Column(Boolean, default=True, index=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )


class StudentAbility(Base):
    __tablename__ = "student_abilities"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(String(32), ForeignKey("students.id"), nullable=False, index=True)
    ability_name = Column(String(64), nullable=False, index=True)
    description = Column(Text, default="")
    source = Column(String(20), default="teacher", index=True)  # teacher / student / parent
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )


class StudentGoal(Base):
    __tablename__ = "student_goals"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(String(32), ForeignKey("students.id"), nullable=False, index=True)
    title = Column(String(128), nullable=False)
    description = Column(Text, default="")
    target_progress = Column(Integer, default=100)
    current_progress = Column(Integer, default=0)
    due_date = Column(Date, nullable=True, index=True)
    is_completed = Column(Boolean, default=False, index=True)
    generated_by = Column(String(20), default="ai", index=True)  # ai / teacher
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        index=True,
    )


class StudentSemesterStats(Base):
    __tablename__ = "student_semester_stats"

    student_id = Column(String(32), ForeignKey("students.id"), primary_key=True, index=True)
    semester = Column(String(20), default="")
    avg_score = Column(Float, default=0)
    attendance_rate = Column(Float, default=0)
    flash_count = Column(Integer, default=0)
    dream = Column(String(128), default="")
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
