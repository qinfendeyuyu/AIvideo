from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.core.config import AppConfig
from app.schemas.project import CharacterProfile, EpisodePlan, Scene


class LLMService:
    def __init__(self, config: AppConfig):
        self.base_url = str(config.get("llm", "base_url", default="")).rstrip("/")
        self.api_key = str(config.get("llm", "api_key", default="local-key"))
        self.model = str(config.get("llm", "model", default=""))
        self.timeout = float(config.get("llm", "timeout_seconds", default=120))
        self.backend = str(config.get("llm", "backend", default="openai_compat"))
        self.options: dict[str, Any] = config.get("llm", "options", default={}) or {}
        self.demo_mode = bool(config.get("project", "demo_mode", default=False))

    @staticmethod
    def _character_bible(characters: list[CharacterProfile]) -> str:
        if not characters:
            return "暂无角色设定；请为本集建立清晰且可复现的主角外观。"
        return "\n".join(
            f"- {item.name}: 外貌={item.appearance}; 服装={item.wardrobe}; "
            f"触发词={', '.join(item.trigger_words) or '无'}"
            for item in characters
        )

    def _demo_plan(
        self,
        title: str,
        premise: str,
        style_prompt: str,
        max_scene_count: int,
        characters: list[CharacterProfile],
    ) -> EpisodePlan:
        """Offline smoke-test storyboard. It is never used unless demo_mode is explicitly on."""
        lead = characters[0] if characters else None
        lead_name = lead.name if lead else "主角"
        appearance = lead.appearance if lead else "black hair, determined eyes, practical futuristic coat"
        wardrobe = lead.wardrobe if lead and lead.wardrobe else "consistent outfit"
        beats = [
            (
                "建立世界与危机",
                f"wide establishing shot, {lead_name} in a world shaped by: {premise}",
                "action",
                f"slow cinematic camera push-in while {lead_name} walks through the location",
            ),
            (
                "主角发现异常",
                f"medium shot, {lead_name}, {appearance}, {wardrobe}, detects the key clue",
                "dialogue",
                "subtle speaking, blinking and a small head turn",
            ),
            (
                "冲突升级",
                f"dynamic two-shot, {lead_name} faces an obstacle, strong depth and contrast",
                "action",
                "clear full-body defensive movement, fast camera tracking, short impact beat",
            ),
            (
                "留下悬念",
                f"dramatic close-up of {lead_name}, unresolved threat, visual cliffhanger",
                "dialogue",
                "restrained speaking, blinking, slow camera push-in",
            ),
        ]
        scenes: list[Scene] = []
        for position in range(max_scene_count):
            beat, visual, motion_kind, motion_prompt = beats[position % len(beats)]
            scenes.append(
                Scene(
                    index=position + 1,
                    visual_prompt=f"{style_prompt}, {visual}, comic panel composition, no text",
                    narration=f"{beat}：{premise}。{lead_name}知道，真正的答案才刚刚浮现。",
                    camera=("wide shot" if position == 0 else "cinematic medium close-up"),
                    motion_kind=motion_kind,
                    motion_prompt=motion_prompt,
                )
            )
        return EpisodePlan(title=title, scenes=scenes)

    @staticmethod
    def _content_to_text(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(
                block.get("text", "") for block in content if isinstance(block, dict)
            )
        raise ValueError("LLM returned an unsupported message content type")

    @staticmethod
    def _parse_json(content: str) -> dict[str, Any]:
        cleaned = content.strip()
        fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re.DOTALL | re.IGNORECASE)
        if fenced:
            cleaned = fenced.group(1)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            # Some OpenAI-compatible backends prepend a short explanation despite the request.
            start, end = cleaned.find("{"), cleaned.rfind("}")
            if start < 0 or end <= start:
                raise
            data = json.loads(cleaned[start : end + 1])
        if not isinstance(data, dict):
            raise ValueError("LLM JSON root must be an object")
        return data

    async def plan_episode(
        self,
        *,
        title: str,
        premise: str,
        style_prompt: str,
        max_scene_count: int,
        characters: list[CharacterProfile],
    ) -> EpisodePlan:
        if max_scene_count < 1:
            raise ValueError("project.max_scene_count must be at least 1")
        if not self.demo_mode and (not self.base_url or not self.model):
            raise RuntimeError("llm.base_url and llm.model are required when demo_mode is false")

        system_prompt = (
            "你是严谨的漫剧导演兼分镜师。仅输出合法 JSON，不要 Markdown。"
            "输出结构严格为: {\"title\":\"\",\"scenes\":[{\"index\":1,"
            "\"visual_prompt\":\"English image prompt\",\"narration\":\"中文旁白\","
            "\"camera\":\"镜头语言\",\"dialogue\":[\"可选对白\"],"
            "\"motion_kind\":\"dialogue 或 action\",\"motion_prompt\":\"English motion prompt\"}]}. "
            f"必须恰好输出 {max_scene_count} 个场景；index 必须从 1 连续编号。"
            "每一镜 visual_prompt 必须明确写出当前出镜角色的英文外貌、服装、景别与光线；"
            "不得在画面提示词中要求文字、水印或分镜编号。"
            "visual_prompt 必须为简洁英文，最多 55 个英文词，以逗号分隔短语。"
            "每镜 narration 必须是一句不超过 16 个汉字的中文旁白，以匹配 2 至 4 秒动态短镜头。"
            "motion_kind=dialogue 只用于说话特写；motion_kind=action 用于走路、奔跑、打斗、闪避、推拉摇移等大幅肢体或镜头动作。"
            "motion_prompt 必须为简洁英文，明确主体动作、动作方向、景别和一个运镜；不得要求文字或水印。"
        )
        if self.demo_mode:
            print("[demo] using built-in storyboard; real LLM backends are skipped.")
            return self._demo_plan(title, premise, style_prompt, max_scene_count, characters)
        user_prompt = (
            f"标题: {title}\n核心设定: {premise}\n美术风格: {style_prompt}\n"
            f"角色圣经:\n{self._character_bible(characters)}\n请直接返回 JSON。"
        )
        openai_payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.45,
            "response_format": {"type": "json_object"},
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        url = f"{self.base_url}/chat/completions"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                if self.backend == "ollama_native":
                    url = f"{self.base_url}/api/chat"
                    native_payload = {
                        "model": self.model,
                        "messages": openai_payload["messages"],
                        "stream": False,
                        "format": "json",
                        "options": {"temperature": 0.45, **self.options},
                        "keep_alive": 0,
                    }
                    response = await client.post(url, json=native_payload)
                elif self.backend == "openai_compat":
                    response = await client.post(url, headers=headers, json=openai_payload)
                else:
                    raise ValueError(f"Unsupported llm.backend: {self.backend}")
                response.raise_for_status()
            response_data = response.json()
            if self.backend == "ollama_native":
                content = self._content_to_text(response_data["message"]["content"])
            else:
                content = self._content_to_text(response_data["choices"][0]["message"]["content"])
            plan = EpisodePlan.model_validate(self._parse_json(content))
            if len(plan.scenes) != max_scene_count:
                raise ValueError(
                    f"LLM returned {len(plan.scenes)} scenes; expected {max_scene_count}"
                )
            return plan
        except (httpx.HTTPError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                f"LLM planning failed at {url}: {exc}. Fix the local model response; no fallback is used "
                "outside demo_mode."
            ) from exc
