import os


class LLMSettings:
    """
    大模型配置（独立文件）
    可通过环境变量覆盖，默认使用本地/离线优先策略。
    """

    # 是否启用真实大模型调用（false 时使用本地模板/回退答案）
    use_real_llm: bool = os.getenv("USE_REAL_LLM", "false").lower() == "true"

    # Ollama 服务配置
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")

    # 预留 OpenAI 兼容配置（当前代码主路径未使用）
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


llm_settings = LLMSettings()
