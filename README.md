# 远山不远（YuanShan）项目文档

## 1. 项目摘要

“远山不远”是一个面向乡村教学场景的 AI 教育平台，采用 **FastAPI + SQLAlchemy + 本地/可选在线大模型** 的后端架构，并通过单页前端 `yuanshan.html` 实现教师端与学生端一体化交互。\
当前已落地的核心能力包括：

- 教师端：登录鉴权、智能备课、作业批改、知识库问答、家校沟通、微课克隆、教师成长档案、心理关怀、工作台动态看板。
- 学生端：梦想（职业）模拟器（支持自定义职业与多节点故事）、心理关怀联动、个人成长档案动态展示。
- 数据侧：学生/教师行为数据沉淀、成长指标聚合、勋章系统、待办事项 CRUD、定时任务刷新统计。

***

## 2. 总体技术栈

- 后端框架：`FastAPI`, `Uvicorn`
- 数据层：`SQLAlchemy 2.x`, `PostgreSQL/SQLite`（开发默认 SQLite）
- 认证授权：`python-jose` JWT + `passlib[bcrypt]`
- AI/LLM：`LocalLLM`（`ctransformers` 本地）+ 可选 `Ollama (Qwen2.5:7b)` + `langchain/langgraph`
- 检索与相似度：`sentence-transformers`, `chromadb`（可扩展）
- 音视频：`openai-whisper`, `ffmpeg` 处理（微课场景）
- 文档导出：`python-docx`, `reportlab`
- 任务调度：`APScheduler`
- 缓存/异步扩展：`redis`, `celery`（已预留）
- 前端：原生 `HTML/CSS/JavaScript`（单文件页面，API 驱动）

***

## 3. 目录结构（核心）

```text
2.远山不远/
├─ yuanshan.html
├─ PROJECT_DOCUMENTATION.md
├─ backend/
│  ├─ main.py
│  ├─ requirements.txt
│  ├─ yuanshan_dev.db
│  └─ app/
│     ├─ main.py
│     ├─ config.py
│     ├─ auth.py
│     ├─ db/
│     ├─ routes/
│     └─ services/
```

<br />

***

## 4. 文件级说明（功能 + 技术栈）

## 4.1 根目录与入口

- `yuanshan.html`\
  功能：教师端与学生端单页应用，负责登录、面板切换、API 调用、动态渲染。\
  技术栈：`HTML/CSS/Vanilla JS`、`fetch`、JWT 本地存储。
- `backend/main.py`\
  功能：后端启动入口（运行 `backend.app.main:app`）。\
  技术栈：`uvicorn`。
- `backend/requirements.txt`\
  功能：项目 Python 依赖清单。\
  技术栈：`pip` 依赖管理。
- `backend/yuanshan_dev.db`\
  功能：本地开发数据库（SQLite）。\
  技术栈：`SQLite`。
- `.tmp_growth_smoke.py`\
  功能：临时烟雾测试脚本（成长档案相关）。\
  技术栈：`Python/TestClient`。

***

## 4.2 应用主干（`backend/app`）

- `backend/app/main.py`\
  功能：创建 FastAPI 应用、挂载路由、启动时建表和种子数据、启动调度任务。\
  技术栈：`FastAPI`, `SQLAlchemy`, `APScheduler`, `CORS`。
- `backend/app/config.py`\
  功能：集中管理环境配置（JWT、数据库、LLM、Redis 等）。\
  技术栈：`os.getenv` 配置模式。
- `backend/app/auth.py`\
  功能：密码哈希、JWT 签发/校验、角色鉴权依赖。\
  技术栈：`passlib[bcrypt]`, `python-jose`, `FastAPI Depends`。
- `backend/app/__init__.py`\
  功能：包标记文件。\
  技术栈：Python 包机制。

***

## 4.3 数据层（`backend/app/db`）

- `backend/app/db/database.py`\
  功能：数据库引擎、会话工厂、`get_db` 依赖注入。\
  技术栈：`SQLAlchemy Engine/Session`。
- `backend/app/db/models.py`\
  功能：定义核心 ORM 模型（用户、学生、备课、作业、家访、微课、心理、成长档案、待办等）。\
  技术栈：`SQLAlchemy ORM`, `JSON/DateTime` 字段建模。
- `backend/app/db/__init__.py`\
  功能：包标记文件。\
  技术栈：Python 包机制。

***

## 4.4 路由层（`backend/app/routes`）

- `auth.py`\
  功能：注册、登录、`/api/me` 用户信息。\
  技术栈：`FastAPI APIRouter`, `Pydantic`, JWT 鉴权。
- `lesson_plan.py`\
  功能：智能备课生成、课标检查、档案保存等接口。\
  技术栈：`FastAPI`, `LangChain/LLM`, 数据落库。
- `homework.py`\
  功能：作业批改任务发起、结果查询、学情数据输出。\
  技术栈：`FastAPI`, 异步任务轮询模式。
- `knowledge.py`\
  功能：知识库检索、问答与类比输出。\
  技术栈：`FastAPI`, 检索服务 + LLM 回答。
- `communication.py`\
  功能：通知生成、家访记录 CRUD、家访建议与对象推荐。\
  技术栈：`FastAPI`, 规则 + LLM 生成。
- `microcourse.py`\
  功能：微课视频分析任务提交、结果查询、名师资源接口。\
  技术栈：`FastAPI`, 音视频处理, 向量匹配。
- `legacy_agents.py`\
  功能：兼容旧版 Agent 接口，避免新旧路由冲突。\
  技术栈：`FastAPI` 兼容层。
- `teacher_growth.py`\
  功能：教师成长档案数据、统计刷新、职称材料导出。\
  技术栈：`FastAPI`, 统计聚合, `python-docx/reportlab`。
- `psychology.py`\
  功能：心理分析、预警列表、今日提醒、周清单 CRUD。\
  技术栈：`FastAPI`, LLM 评估, 数据缓存。
- `dream.py`\
  功能：梦想模拟器职业列表、故事推进、路径生成、插画生成。\
  技术栈：`FastAPI`, LLM 生成, JSON 场景引擎。
- `student_archive.py`\
  功能：学生成长档案聚合、能力管理、闪光时刻、目标生成。\
  技术栈：`FastAPI`, SQL 聚合, LLM 文本生成。
- `teacher_dashboard.py`\
  功能：教师首页看板聚合、待办事项 CRUD。\
  技术栈：`FastAPI`, 看板聚合服务。
- `routes/__init__.py`\
  功能：包标记文件。\
  技术栈：Python 包机制。

***

## 4.5 服务层（`backend/app/services`）

- `local_llm.py`\
  功能：统一大模型调用入口（本地 ctransformers + Ollama 回退）。\
  技术栈：`ctransformers`, `langchain_community.Ollama`。
- `lesson_plan_generator.py`\
  功能：生成复式课堂备课方案。\
  技术栈：`LangChain/Ollama`, 结构化文本生成。
- `standard_checker.py`\
  功能：课标覆盖检查与反馈。\
  技术栈：规则 + LLM 校核。
- `homework_corrector.py`\
  功能：作业 OCR/判题/统计与学情输出。\
  技术栈：OCR + LLM + 规则评分。
- `knowledge_retriever.py`\
  功能：知识点检索、类比素材拼接。\
  技术栈：SQL 查询 + 简单检索策略。
- `qa_engine.py`\
  功能：教学问答生成（基于知识检索上下文）。\
  技术栈：检索增强 + `LocalLLM`。
- `notice_generator.py`\
  功能：家校通知润色与结构化输出。\
  技术栈：提示词工程 + `LocalLLM`。
- `visit_suggestion.py`\
  功能：家访对象推荐与家访内容建议。\
  技术栈：规则融合 + `LocalLLM`。
- `video_processor.py`\
  功能：微课视频转写/提取文本。\
  技术栈：`ffmpeg`, `whisper`。
- `master_matcher.py`\
  功能：名师课程匹配与相似资源召回。\
  技术栈：`sentence-transformers`, 向量/关键词混合检索。
- `comparison_engine.py`\
  功能：教师微课与名师课差异分析，输出改进建议。\
  技术栈：对比提示词 + `LocalLLM`。
- `microcourse_service.py`\
  功能：微课异步任务编排与状态管理。\
  技术栈：内存任务池 + 服务编排。
- `teacher_stats.py`\
  功能：教师成长维度统计与缓存。\
  技术栈：SQL 聚合 + `Redis`（可选）。
- `badge_service.py`\
  功能：勋章解锁判定与进度计算。\
  技术栈：规则引擎（数据库配置驱动）。
- `title_material_generator.py`\
  功能：教师职称材料导出（DOCX/PDF）。\
  技术栈：`python-docx`, `reportlab`。
- `psychology_service.py`\
  功能：心理材料分析、预警等级判定、建议生成。\
  技术栈：规则 + `LocalLLM`。
- `psychology_scheduler.py`\
  功能：心理提醒与周清单定时刷新。\
  技术栈：`APScheduler`。
- `custom_career.py`\
  功能：自定义职业模板生成（故事、技能、知识图谱）。\
  技术栈：提示词生成 + `LocalLLM`。
- `story_engine.py`\
  功能：梦想故事节点推进、选择反馈、最终路径生成。\
  技术栈：状态机式流程 + `LocalLLM`。
- `illustration_generator.py`\
  功能：梦想场景 AI 插画（简笔画 SVG）生成。\
  技术栈：LLM 元素选择 + SVG 绘制。
- `student_archive.py`\
  功能：学生档案聚合（基础信息、成绩趋势、能力、闪光、目标）。\
  技术栈：SQL 聚合 + 缓存表刷新。
- `flash_polisher.py`\
  功能：闪光时刻文本润色与鼓励语生成。\
  技术栈：提示词工程 + `LocalLLM`。
- `goal_generator.py`\
  功能：阶段目标 AI 生成并持久化。\
  技术栈：`LocalLLM` + SQL 数据驱动。
- `student_archive_scheduler.py`\
  功能：学生学期统计定时刷新。\
  技术栈：`APScheduler`。
- `dashboard_service.py`\
  功能：教师工作台首页聚合数据（统计、提醒、待办、勋章）。\
  技术栈：SQL 聚合 + 规则计算。
- `asr.py`\
  功能：语音识别封装（用于语音输入场景）。\
  技术栈：`whisper`/ASR 封装。
- `standard_checker.py`\
  功能：教学方案规范与课标适配检查。\
  技术栈：规则校验 + LLM 辅助。
- `services/__init__.py`\
  功能：包标记文件。\
  技术栈：Python 包机制。

***

## 4.6 包初始化文件

- `backend/__init__.py`、`backend/app/routes/__init__.py`、`backend/app/services/__init__.py`、`backend/app/db/__init__.py`\
  功能：Python 包初始化/命名空间声明。\
  技术栈：Python 模块系统。

***

## 5. LLM 配置说明 (`llm_config.py`)

项目的大模型配置由 `backend/app/llm_config.py` 管理，采用环境变量覆盖的机制。默认采用离线优先/本地模板策略（即不真正调用大模型以保证开发环境快速启动）。当需要真实 AI 能力时，可通过配置以下环境变量开启：

- `USE_REAL_LLM`：是否启用真实大模型。设置为 `true` 时，系统将真正向配置的 LLM 服务发起请求；默认值为 `false`（使用模拟数据/回退答案）。
- **Ollama 本地模型配置**（推荐）：
  - `OLLAMA_BASE_URL`：Ollama 服务的访问地址，默认为 `http://localhost:11434`。
  - `OLLAMA_MODEL`：所使用的模型名称，默认为 `qwen2.5:7b`。
- **OpenAI 兼容配置**（预留扩展）：
  - `OPENAI_BASE_URL`：OpenAI 兼容接口地址。
  - `OPENAI_API_KEY`：API 密钥。
  - `OPENAI_MODEL`：模型名称，默认为 `gpt-4o-mini`。

> **配置方式**：在运行后端服务前，通过 `export` 命令（Linux/macOS）设置环境变量。

***

## 6. 全流程使用指南

为了能够完整体验“远山不远”项目的所有功能（含 AI 真实生成），请按照以下步骤进行操作：

### 步骤 1：环境与依赖准备
1. 确保已安装 Python 环境。
2. 进入项目根目录并安装依赖（如需）：
   ```bash
   cd  ../yuanshan_Agent/yuanshan_Agent
   pip install -r backend/requirements.txt
   ```

### 步骤 2：准备本地大模型服务（Ollama）
本项目默认配置推荐使用本地部署的 Qwen 模型：
1. 安装 [Ollama](https://ollama.com/) 并启动。
2. 在终端拉取并运行模型（此过程可能需要下载几十GB文件）：
   ```bash
   ollama run qwen2.5:7b
   ```
3. 确保 Ollama 服务在 `http://localhost:11434` 正常运行，并可接收请求。

### 步骤 3：配置并启动后端服务
1. 在终端设置环境变量以启用真实大模型：
   ```bash
   export USE_REAL_LLM=true
   export OLLAMA_BASE_URL=http://localhost:11434
   export OLLAMA_MODEL=qwen2.5:7b
   ```
2. 启动后端服务（推荐使用模块方式启动以避免相对导入报错）：
   ```bash
   python -m backend.main
   ```
   *(服务默认启动在 `http://0.0.0.0:8000`)*

### 步骤 4：前端交互体验
1. 在浏览器中直接双击打开项目根目录下的 `yuanshan.html` 文件，或者使用 VSCode Live Server 插件打开。
2. **账号登录**（后端内置了种子测试账号）：
   - **教师端**体验：输入账号 `teacher001`，密码 `123456`
   - **学生端**体验：输入账号 `student001`，密码 `123456`
3. **核心功能流转验证**：
   - 教师端登录后：进入工作台，可体验**智能备课**（输入课题生成教案）、**生成家校通知**（选择学生与情境自动润色）、**批改作业**等。此时后端会调用 Ollama 进行真实推演并返回结果。
   - 学生端登录后：进入**梦想模拟器**，可以设定自己的梦想职业，系统会根据大模型生成成长故事节点，并支持多分支选择。

***
