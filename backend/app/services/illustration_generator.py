import hashlib
import json
from typing import Any, Dict, List, Tuple

from backend.app.services.local_llm import LocalLLM


ALLOWED_ELEMENTS = [
    "student",
    "teacher",
    "book",
    "computer",
    "microscope",
    "rocket",
    "animal",
    "tree",
    "toolbox",
    "clinic",
    "classroom",
    "farm",
    "workbench",
    "notebook",
    "team",
]


class IllustrationGenerator:
    def __init__(self) -> None:
        self.llm = LocalLLM()

    def generate(self, career_name: str, scene: str, narration: str) -> Dict[str, str]:
        tags = self._choose_elements(career_name, scene, narration)
        svg = self._render_svg(career_name, scene, tags)
        return {
            "svg": svg,
            "alt": f"{career_name}职业体验插画：{scene}",
            "style": "simple-line-art",
        }

    def _choose_elements(self, career_name: str, scene: str, narration: str) -> List[str]:
        prompt = f"""
你是儿童插画分镜助手。请从以下白名单中挑选最贴合场景的3个元素，只输出JSON：
{{"elements":["student","book","classroom"]}}
白名单：{ALLOWED_ELEMENTS}
职业：{career_name}
场景：{scene}
叙述：{narration}
要求：简笔画、积极、无恐怖内容。
""".strip()
        fallback = {"elements": self._fallback_elements(career_name, scene, narration)}
        raw = self.llm.generate(prompt, fallback_answer=json.dumps(fallback, ensure_ascii=False))
        elements = self._parse_elements(raw)
        if not elements:
            elements = fallback["elements"]
        cleaned = []
        for item in elements:
            key = str(item).strip().lower()
            if key in ALLOWED_ELEMENTS and key not in cleaned:
                cleaned.append(key)
        if not cleaned:
            cleaned = fallback["elements"]
        return cleaned[:3]

    def _parse_elements(self, raw: str) -> List[str]:
        if not raw:
            return []
        text = raw.strip()
        try:
            data = json.loads(text)
            if isinstance(data, dict) and isinstance(data.get("elements"), list):
                return [str(v) for v in data["elements"]]
        except Exception:
            pass
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                data = json.loads(text[start : end + 1])
                if isinstance(data, dict) and isinstance(data.get("elements"), list):
                    return [str(v) for v in data["elements"]]
            except Exception:
                return []
        return []

    def _fallback_elements(self, career_name: str, scene: str, narration: str) -> List[str]:
        text = f"{career_name} {scene} {narration}"
        mapping: List[Tuple[str, str]] = [
            ("宇航", "rocket"),
            ("航天", "rocket"),
            ("兽医", "animal"),
            ("动物", "animal"),
            ("老师", "teacher"),
            ("课堂", "classroom"),
            ("编程", "computer"),
            ("工程", "toolbox"),
            ("科学", "microscope"),
            ("农", "farm"),
        ]
        elements = ["student"]
        for keyword, item in mapping:
            if keyword in text and item not in elements:
                elements.append(item)
        if "book" not in elements:
            elements.append("book")
        return elements[:3]

    def _render_svg(self, career_name: str, scene: str, elements: List[str]) -> str:
        seed = int(hashlib.md5(f"{career_name}-{scene}".encode("utf-8")).hexdigest()[:8], 16)
        bg_hue = 80 + seed % 60
        panel = [
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 260" role="img" aria-label="梦想场景简笔画">',
            f'<rect x="0" y="0" width="640" height="260" rx="18" fill="hsl({bg_hue},45%,94%)"/>',
            '<rect x="22" y="20" width="596" height="220" rx="14" fill="#fff" stroke="#d8d2c8" stroke-width="2"/>',
            '<text x="36" y="52" font-size="18" font-family="Arial" fill="#2d5016">AI简笔画场景</text>',
        ]
        x = 70
        for tag in elements:
            panel.extend(self._element_svg(tag, x, 145))
            x += 185
        panel.append('<line x1="40" y1="205" x2="600" y2="205" stroke="#d8d2c8" stroke-width="2"/>')
        panel.append("</svg>")
        return "".join(panel)

    def _element_svg(self, tag: str, cx: int, cy: int) -> List[str]:
        if tag == "student":
            return [
                f'<circle cx="{cx}" cy="{cy-48}" r="20" fill="none" stroke="#3d6b22" stroke-width="3"/>',
                f'<rect x="{cx-18}" y="{cy-26}" width="36" height="52" rx="10" fill="none" stroke="#3d6b22" stroke-width="3"/>',
                f'<line x1="{cx-18}" y1="{cy-8}" x2="{cx-38}" y2="{cy+10}" stroke="#3d6b22" stroke-width="3"/>',
                f'<line x1="{cx+18}" y1="{cy-8}" x2="{cx+38}" y2="{cy+10}" stroke="#3d6b22" stroke-width="3"/>',
            ]
        if tag == "teacher":
            return [
                f'<circle cx="{cx}" cy="{cy-52}" r="18" fill="none" stroke="#2f5f74" stroke-width="3"/>',
                f'<rect x="{cx-16}" y="{cy-30}" width="32" height="56" rx="8" fill="none" stroke="#2f5f74" stroke-width="3"/>',
                f'<line x1="{cx+18}" y1="{cy-16}" x2="{cx+42}" y2="{cy-30}" stroke="#2f5f74" stroke-width="3"/>',
            ]
        if tag == "rocket":
            return [
                f'<path d="M{cx-12},{cy-40} Q{cx},{cy-92} {cx+12},{cy-40} Z" fill="none" stroke="#c05f3d" stroke-width="3"/>',
                f'<rect x="{cx-12}" y="{cy-40}" width="24" height="58" rx="8" fill="none" stroke="#c05f3d" stroke-width="3"/>',
                f'<circle cx="{cx}" cy="{cy-18}" r="7" fill="none" stroke="#c05f3d" stroke-width="3"/>',
            ]
        if tag == "animal":
            return [
                f'<rect x="{cx-34}" y="{cy-28}" width="68" height="36" rx="12" fill="none" stroke="#7a6a52" stroke-width="3"/>',
                f'<circle cx="{cx+40}" cy="{cy-18}" r="13" fill="none" stroke="#7a6a52" stroke-width="3"/>',
                f'<line x1="{cx-20}" y1="{cy+8}" x2="{cx-20}" y2="{cy+24}" stroke="#7a6a52" stroke-width="3"/>',
                f'<line x1="{cx+8}" y1="{cy+8}" x2="{cx+8}" y2="{cy+24}" stroke="#7a6a52" stroke-width="3"/>',
            ]
        if tag == "computer":
            return [
                f'<rect x="{cx-36}" y="{cy-44}" width="72" height="44" rx="6" fill="none" stroke="#4b6980" stroke-width="3"/>',
                f'<line x1="{cx}" y1="{cy}" x2="{cx}" y2="{cy+18}" stroke="#4b6980" stroke-width="3"/>',
                f'<rect x="{cx-24}" y="{cy+18}" width="48" height="10" rx="4" fill="none" stroke="#4b6980" stroke-width="3"/>',
            ]
        if tag == "book" or tag == "notebook":
            return [
                f'<rect x="{cx-34}" y="{cy-36}" width="30" height="46" rx="4" fill="none" stroke="#5a8a35" stroke-width="3"/>',
                f'<rect x="{cx+4}" y="{cy-36}" width="30" height="46" rx="4" fill="none" stroke="#5a8a35" stroke-width="3"/>',
                f'<line x1="{cx}" y1="{cy-36}" x2="{cx}" y2="{cy+10}" stroke="#5a8a35" stroke-width="2"/>',
            ]
        if tag == "classroom":
            return [
                f'<rect x="{cx-40}" y="{cy-46}" width="80" height="50" rx="8" fill="none" stroke="#3d6b22" stroke-width="3"/>',
                f'<line x1="{cx-18}" y1="{cy-16}" x2="{cx+18}" y2="{cy-16}" stroke="#3d6b22" stroke-width="2"/>',
                f'<line x1="{cx-14}" y1="{cy+4}" x2="{cx+14}" y2="{cy+4}" stroke="#3d6b22" stroke-width="2"/>',
            ]
        if tag == "microscope":
            return [
                f'<path d="M{cx-14},{cy-18} L{cx+12},{cy-44}" fill="none" stroke="#4a8fa8" stroke-width="4"/>',
                f'<circle cx="{cx+16}" cy="{cy-48}" r="7" fill="none" stroke="#4a8fa8" stroke-width="3"/>',
                f'<rect x="{cx-28}" y="{cy-4}" width="56" height="8" rx="4" fill="none" stroke="#4a8fa8" stroke-width="3"/>',
            ]
        if tag == "farm":
            return [
                f'<rect x="{cx-36}" y="{cy-18}" width="72" height="26" fill="none" stroke="#6b7a5e" stroke-width="3"/>',
                f'<path d="M{cx-40},{cy-18} L{cx},{cy-50} L{cx+40},{cy-18}" fill="none" stroke="#6b7a5e" stroke-width="3"/>',
            ]
        if tag == "toolbox" or tag == "workbench":
            return [
                f'<rect x="{cx-34}" y="{cy-20}" width="68" height="30" rx="6" fill="none" stroke="#a56d32" stroke-width="3"/>',
                f'<line x1="{cx-10}" y1="{cy-28}" x2="{cx+10}" y2="{cy-28}" stroke="#a56d32" stroke-width="3"/>',
            ]
        if tag == "clinic":
            return [
                f'<rect x="{cx-34}" y="{cy-42}" width="68" height="52" rx="8" fill="none" stroke="#9a4c61" stroke-width="3"/>',
                f'<line x1="{cx}" y1="{cy-30}" x2="{cx}" y2="{cy-12}" stroke="#9a4c61" stroke-width="3"/>',
                f'<line x1="{cx-9}" y1="{cy-21}" x2="{cx+9}" y2="{cy-21}" stroke="#9a4c61" stroke-width="3"/>',
            ]
        if tag == "team":
            return [
                f'<circle cx="{cx-16}" cy="{cy-34}" r="12" fill="none" stroke="#3d6b22" stroke-width="3"/>',
                f'<circle cx="{cx+16}" cy="{cy-34}" r="12" fill="none" stroke="#3d6b22" stroke-width="3"/>',
                f'<rect x="{cx-30}" y="{cy-18}" width="60" height="30" rx="10" fill="none" stroke="#3d6b22" stroke-width="3"/>',
            ]
        if tag == "tree":
            return [
                f'<circle cx="{cx}" cy="{cy-34}" r="20" fill="none" stroke="#4f7a33" stroke-width="3"/>',
                f'<rect x="{cx-4}" y="{cy-14}" width="8" height="24" fill="none" stroke="#4f7a33" stroke-width="3"/>',
            ]
        return self._element_svg("student", cx, cy)
