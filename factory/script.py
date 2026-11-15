"""Сценарий: тема -> структурированный сценарий со сценами (Claude)."""

import anthropic

from . import config
from .models import Scene, VideoScript

SYSTEM = """You write scripts for "{channel}", a faceless YouTube channel that teaches \
developers and founders how to automate real work with AI tools.

Every video shows one working automation end to end: the problem, the stack, the steps, \
the result, and what it costs to run. The audience is technical and impatient, so open with \
the outcome in the first sentence, name specific tools and numbers, and never pad. Do not \
invent benchmarks, revenue figures or customer stories: if a number is not given in the \
topic, describe the mechanism instead of quoting a figure.

Write narration to be spoken aloud: short sentences, no markdown, no emoji, no stage \
directions. Aim for 8 to 12 scenes of 2 to 4 sentences each, about 4 to 6 minutes in total.

Each scene needs a visual prompt for an image model. Describe one concrete, distinct shot \
per scene (a different subject, angle or setting each time) in a consistent clean, modern, \
cinematic style. No on-screen text, logos, or real people's likenesses.

{ending}"""

# Ссылка попадает в описание только при заданном PRODUCT_URL (см. youtube.py), поэтому без него
# ролик не должен на неё ссылаться.
ENDING_WITH_LINK = "End the last scene with a single plain call to action pointing to the link in the description."
ENDING_WITHOUT_LINK = ("End the last scene with a one-sentence recap of the result. Do not mention a link, "
                       "a template, a download or anything to be found below the video, anywhere in the title, "
                       "the description or the narration: none is provided with this video.")


def system_prompt() -> str:
    ending = ENDING_WITH_LINK if config.PRODUCT_URL else ENDING_WITHOUT_LINK
    return SYSTEM.format(channel=config.CHANNEL_NAME, ending=ending)


def generate_script(topic: str) -> VideoScript:
    client = anthropic.Anthropic()
    response = client.messages.parse(
        model="claude-opus-5-5",
        max_tokens=16000,
        output_config={"effort": "high"},
        system=system_prompt(),
        messages=[{"role": "user", "content": f"Write the script for this video topic:\n\n{topic}"}],
        output_format=VideoScript,
    )
    if response.stop_reason == "refusal":
        raise RuntimeError(f"Модель отказалась писать сценарий по теме: {topic}")
    if response.stop_reason == "max_tokens" or response.parsed_output is None:
        raise RuntimeError("Сценарий не уместился в лимит токенов или не разобрался")
    return response.parsed_output


def mock_script(topic: str) -> VideoScript:
    """Сценарий-заглушка для --dry-run: проверяет сборку без обращения к API."""
    lines = [
        f"This video shows how to build {topic} from start to finish.",
        "First we look at the manual process and where the time goes every week.",
        "Then we connect three tools so that the whole thing runs on a schedule.",
        "Here is the result, what it costs to run, and where to get the template.",
    ]
    return VideoScript(
        title=f"[DRY RUN] {topic}"[:70],
        description="Dry run. No API calls were made.",
        tags=["dry-run"],
        thumbnail_text="DRY RUN",
        scenes=[Scene(narration=t, visual_prompt=f"placeholder shot {i + 1}") for i, t in enumerate(lines)],
    )
