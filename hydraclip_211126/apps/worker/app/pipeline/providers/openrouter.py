"""OpenRouter provider that turns a topic into a structured video plan.

OpenRouter exposes an OpenAI-compatible API, so we call `/chat/completions`
directly with httpx. The model only produces JSON data - it never writes
React/JS code. The Remotion composition is fixed and receives the plan as
input props.
"""

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

PALETTES = [
    ("#ffd166", "#071a3a", "#6a1b9a"),
    ("#7bf1a8", "#032b1d", "#0b6e4f"),
    ("#8ecae6", "#031b2b", "#1b4965"),
    ("#ff9f1c", "#2b0b00", "#8a2d00"),
    ("#c77dff", "#16002b", "#5a189a"),
    ("#ff6b6b", "#2b0000", "#7f1d1d"),
]

HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


@dataclass
class VideoPlan:
    """Validated data passed to the Remotion composition."""

    title: str
    narration: str
    scenes: list[str]
    accent: str
    background_start: str
    background_end: str

    def to_input_props(
        self,
        audio_src: Optional[str],
        duration_seconds: float,
        images: Optional[list[dict[str, Any]]] = None,
        subtitle: str = "Made with HydraClip",
    ) -> dict[str, Any]:
        image_list = images or []
        scenes = []
        for index, text in enumerate(self.scenes):
            image = image_list[index % len(image_list)] if image_list else None
            scenes.append(
                {
                    "text": text,
                    "image": image.get("src") if image else None,
                    "credit": image.get("credit") if image else None,
                }
            )

        return {
            "title": self.title,
            "subtitle": subtitle,
            "scenes": scenes,
            "audioSrc": audio_src,
            "durationSeconds": round(float(duration_seconds), 2),
            "accent": self.accent,
            "backgroundStart": self.background_start,
            "backgroundEnd": self.background_end,
            "brand": "HYDRACLIP",
        }


def _pick_palette(seed: str) -> tuple[str, str, str]:
    index = sum(ord(char) for char in seed) % len(PALETTES)
    return PALETTES[index]


def _clean_hex(value: Any, fallback: str) -> str:
    if isinstance(value, str) and HEX_RE.match(value.strip()):
        return value.strip()
    return fallback


def build_fallback_plan(
    topic: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
) -> VideoPlan:
    """Deterministic plan used when no API key is configured or the call fails."""
    topic = (topic or "this topic").strip()
    label = (title or topic).strip()
    accent, bg_start, bg_end = _pick_palette(topic)

    scenes = [
        label[:80],
        f"What most people miss about {topic}",
        "The short version:",
        "Start with the surprising detail.",
        "Then connect it to what you already know.",
        "Finally, make one small change today.",
        "Follow for more.",
    ]
    narration = (
        f"{label}. "
        f"{description or ''} "
        f"Here is what most people miss about {topic}. "
        "Start with the surprising detail, then connect it to something you "
        "already know. That connection is what makes it stick. "
        "Finally, make one small change today and see the difference. "
        "Follow for more."
    ).strip()

    return VideoPlan(
        title=label,
        narration=narration,
        scenes=scenes,
        accent=accent,
        background_start=bg_start,
        background_end=bg_end,
    )


class OpenRouterProvider:
    """Calls OpenRouter and parses a validated :class:`VideoPlan`."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        app_url: Optional[str] = None,
    ):
        self.api_key = api_key if api_key is not None else settings.openrouter_api_key
        self.base_url = (
            base_url or settings.openrouter_base_url
        ).rstrip("/")
        self.model = model or settings.openrouter_model
        self.app_url = app_url or settings.app_url

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    async def generate_plan(
        self,
        topic: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        duration_seconds: int = 30,
    ) -> VideoPlan:
        if not self.enabled:
            logger.warning(
                "OPENROUTER_API_KEY is not set - using the deterministic fallback plan"
            )
            return build_fallback_plan(topic, title, description)

        messages = self._build_messages(topic, title, description, duration_seconds)
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 1200,
            "response_format": {"type": "json_object"},
        }

        try:
            data = await self._post(payload)
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            logger.warning(
                "OpenRouter rejected JSON mode (HTTP %s); retrying without response_format",
                status,
            )
            if status in (400, 404, 422):
                payload.pop("response_format", None)
                try:
                    data = await self._post(payload)
                except Exception as retry_exc:
                    logger.error("OpenRouter retry failed: %s", retry_exc)
                    return build_fallback_plan(topic, title, description)
            else:
                logger.error("OpenRouter request failed: %s", exc)
                return build_fallback_plan(topic, title, description)
        except Exception as exc:
            logger.error("OpenRouter request failed: %s", exc)
            return build_fallback_plan(topic, title, description)

        content = self._extract_content(data)
        if not content:
            logger.error("OpenRouter returned no text content")
            return build_fallback_plan(topic, title, description)

        plan = self._parse_plan(content, topic, title, description)
        if plan is None:
            logger.error("OpenRouter returned unusable JSON; using fallback plan")
            return build_fallback_plan(topic, title, description)
        return plan

    def _build_messages(
        self,
        topic: str,
        title: Optional[str],
        description: Optional[str],
        duration_seconds: int,
    ) -> list[dict[str, str]]:
        system = (
            "You are a short-form vertical video planner. "
            "Return ONLY valid JSON. Never return markdown, code fences or commentary."
        )
        user = f"""Create a plan for a {duration_seconds}-second vertical short about: {topic}

Known title: {title or "(invent one)"}
Known description: {description or "(none)"}

Return exactly this JSON shape:
{{
  "title": "short catchy title, max 70 characters",
  "narration": "spoken voiceover, 50-110 words, no stage directions, no emojis",
  "scenes": [{{"text": "on-screen caption, max 9 words"}}],
  "accent": "#RRGGBB",
  "background_start": "#RRGGBB",
  "background_end": "#RRGGBB"
}}

Rules:
- 5 to 8 scenes.
- The scenes should tell one clear story in order.
- The narration must be speakable prose for a text-to-speech voice.
- Use a dark background gradient and one bright accent colour.
- Output JSON only."""
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

    async def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.app_url,
            "X-Title": "HydraClip",
        }
        timeout = httpx.Timeout(90.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    @staticmethod
    def _extract_content(data: dict[str, Any]) -> str:
        choices = data.get("choices")
        if isinstance(choices, list) and choices:
            message = choices[0].get("message") or {}
            content = message.get("content")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts = [
                    part.get("text", "")
                    for part in content
                    if isinstance(part, dict)
                ]
                return "".join(parts)

        # Responses API fallback shape
        if isinstance(data.get("output_text"), str):
            return data["output_text"]
        for item in data.get("output", []) or []:
            for part in item.get("content", []) or []:
                if part.get("type") in ("output_text", "text"):
                    return part.get("text", "")
        return ""

    def _parse_plan(
        self,
        content: str,
        topic: str,
        title: Optional[str],
        description: Optional[str],
    ) -> Optional[VideoPlan]:
        raw = content.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-zA-Z]*\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None

        try:
            parsed = json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            return None
        if not isinstance(parsed, dict):
            return None

        accent_fallback, bg_start_fallback, bg_end_fallback = _pick_palette(
            topic or title or "hydraclip"
        )

        scenes: list[str] = []
        raw_scenes = parsed.get("scenes")
        if isinstance(raw_scenes, list):
            for scene in raw_scenes[:10]:
                text: Any = None
                if isinstance(scene, str):
                    text = scene
                elif isinstance(scene, dict):
                    text = (
                        scene.get("text")
                        or scene.get("caption")
                        or scene.get("description")
                    )
                if isinstance(text, str) and text.strip():
                    scenes.append(text.strip()[:140])
        if not scenes:
            return None

        narration = parsed.get("narration") or parsed.get("script")
        if not isinstance(narration, str) or not narration.strip():
            narration = " ".join(scenes)

        plan_title = parsed.get("title") or title or topic
        if not isinstance(plan_title, str) or not plan_title.strip():
            plan_title = topic
        plan_title = plan_title.strip()[:100]

        return VideoPlan(
            title=plan_title,
            narration=narration.strip(),
            scenes=scenes,
            accent=_clean_hex(parsed.get("accent"), accent_fallback),
            background_start=_clean_hex(
                parsed.get("background_start"), bg_start_fallback
            ),
            background_end=_clean_hex(
                parsed.get("background_end"), bg_end_fallback
            ),
        )
