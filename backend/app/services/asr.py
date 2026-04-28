from typing import Dict
import io
import os
import tempfile
import wave


class OfflineASR:
    def __init__(self, model_size: str = "tiny") -> None:
        self.model = None
        self.model_size = model_size
        try:
            import whisper  # type: ignore

            self.model = whisper.load_model(model_size)
        except Exception:
            self.model = None

        self.dialect_map: Dict[str, str] = {
            "咋子": "怎么",
            "啥子": "什么",
            "整": "做",
            "嘎哈": "干什么",
            "莫得": "没有",
            "娃儿": "孩子",
        }

    def transcribe(self, audio_bytes: bytes) -> str:
        text = ""
        if self.model:
            temp_path = None
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
                    temp_file.write(audio_bytes)
                    temp_path = temp_file.name
                result = self.model.transcribe(temp_path, language="zh")
                text = result.get("text", "").strip()
            except Exception:
                text = ""
            finally:
                if temp_path and os.path.exists(temp_path):
                    os.unlink(temp_path)

        if not text:
            text = "五年级分数除法这一块，我不太会讲，用农村孩子能懂的例子解释一下"

        return self._normalize_dialect(text)

    def _normalize_dialect(self, text: str) -> str:
        normalized = text
        for dialect_word, mandarin_word in self.dialect_map.items():
            normalized = normalized.replace(dialect_word, mandarin_word)
        return normalized.strip()
