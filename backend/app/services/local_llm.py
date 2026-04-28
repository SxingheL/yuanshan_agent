from backend.app.llm_config import llm_settings


class LocalLLM:
    def __init__(self, model_path: str = "models/qwen-1.8b-int8.bin") -> None:
        self.model_path = model_path
        self.model = None
        try:
            from ctransformers import AutoModelForCausalLM  # type: ignore

            self.model = AutoModelForCausalLM.from_pretrained(
                model_path,
                model_type="qwen",
                max_new_tokens=256,
                temperature=0.7,
                top_p=0.9,
                repetition_penalty=1.1,
                threads=4,
            )
        except Exception:
            self.model = None

    def generate(self, prompt: str, fallback_answer: str = "") -> str:
        if self.model:
            try:
                return str(self.model(prompt)).strip()
            except Exception:
                pass

        if llm_settings.use_real_llm:
            try:
                from langchain_community.llms import Ollama  # type: ignore

                llm = Ollama(
                    model=llm_settings.ollama_model,
                    base_url=llm_settings.ollama_base_url,
                )
                return str(llm.invoke(prompt)).strip()
            except Exception:
                pass

        return fallback_answer.strip()
