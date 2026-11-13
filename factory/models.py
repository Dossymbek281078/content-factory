from pydantic import BaseModel, Field


class Scene(BaseModel):
    narration: str = Field(description="What the narrator says in this scene, 2-4 sentences.")
    visual_prompt: str = Field(
        description="Prompt for an image/video model: one concrete shot, no text or logos in frame."
    )


class VideoScript(BaseModel):
    title: str = Field(description="YouTube title, under 70 characters.")
    description: str = Field(description="YouTube description, 2-3 short paragraphs.")
    tags: list[str]
    thumbnail_text: str = Field(description="3-5 words for the thumbnail.")
    scenes: list[Scene]
