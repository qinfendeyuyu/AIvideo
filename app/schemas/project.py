from pydantic import BaseModel, Field, field_validator, model_validator


from typing import Literal


class CharacterProfile(BaseModel):
    """Compact character bible injected into both screenplay and image prompts."""

    name: str = Field(..., min_length=1, max_length=80)
    appearance: str = Field(..., min_length=10, max_length=800)
    wardrobe: str = Field("", max_length=500)
    voice: str = Field("narrator", min_length=1, max_length=80)
    trigger_words: list[str] = Field(default_factory=list, max_length=12)


class EpisodeRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    premise: str = Field(..., min_length=10, max_length=2000)
    style_prompt: str = Field(
        "cinematic comic, high detail, dramatic lighting, consistent characters",
        min_length=5,
        max_length=500,
    )
    characters: list[CharacterProfile] = Field(default_factory=list, max_length=20)
    run_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{3,80}$")
    resume: bool = False
    seed: int | None = Field(default=None, ge=0, le=4_294_967_295)


class Scene(BaseModel):
    index: int = Field(..., ge=1)
    visual_prompt: str = Field(..., min_length=10, max_length=4000)
    narration: str = Field(..., min_length=1, max_length=2000)
    camera: str = Field("", max_length=300)
    dialogue: list[str] = Field(default_factory=list, max_length=12)
    # Dialogue shots use the verified talking-head backend. Action intent is
    # retained for a real T2V/I2V backend without changing screenplay format.
    motion_kind: Literal["dialogue", "action"] = "dialogue"
    motion_prompt: str = Field("", max_length=800)


class EpisodePlan(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    scenes: list[Scene] = Field(..., min_length=1, max_length=40)

    @field_validator("scenes")
    @classmethod
    def scene_indices_must_be_unique(cls, scenes: list[Scene]) -> list[Scene]:
        indices = [scene.index for scene in scenes]
        if len(indices) != len(set(indices)):
            raise ValueError("scene indices must be unique")
        return scenes

    @model_validator(mode="after")
    def scene_indices_must_be_contiguous(self) -> "EpisodePlan":
        actual = sorted(scene.index for scene in self.scenes)
        expected = list(range(1, len(self.scenes) + 1))
        if actual != expected:
            raise ValueError(f"scene indices must be contiguous from 1, got {actual}")
        return self


class EpisodeResult(BaseModel):
    title: str
    scene_count: int
    output_video: str
    output_dir: str
    manifest_file: str
    subtitle_file: str | None = None
    status: str = "completed"
