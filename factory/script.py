"""Сценарий: тема -> структурированный сценарий со сценами (Claude)."""

import http.client
import re
import urllib.request

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
directions.

Nobody has run this automation, so present it as a design and the steps to build it. Do not claim results, \
speed, accuracy or guarantees for it ("runs in seconds", "never misses", "posts itself", "verified report", \
"numbers are never invented"); say instead what the code does and what to measure when the viewer runs it.

{api_facts}

Aim for 8 to 12 scenes of 2 to 4 sentences each, about 4 to 6 minutes in total.

Each scene needs a visual prompt for an image model. Describe one concrete, distinct shot \
per scene (a different subject, angle or setting each time) in a consistent clean, modern, \
cinematic style. No on-screen text, logos, or real people's likenesses. Image models draw \
fake letters on anything that normally carries writing, so never show paper, documents, invoices, \
receipts, books, screens, monitors, code, spreadsheets, charts, dashboards, signs, labels or database \
tables: use abstract shapes, light, objects and places instead.

{ending}"""

# Ссылка попадает в описание только при заданном PRODUCT_URL (см. youtube.py), поэтому без него
# ролик не должен на неё ссылаться.
ENDING_WITH_LINK = "End the last scene with a single plain call to action pointing to the link in the description."
ENDING_WITHOUT_LINK = ("End the last scene with a one-sentence recap of the result. Do not mention a link, "
                       "a template, a download or anything to be found below the video, anywhere in the title, "
                       "the description or the narration: none is provided with this video.")


# Признаки обещания чего-то «под видео». Ловят и сценарии из кэша, написанные до правила выше.
# Ищутся фразы-указатели «куда-то за пределы ролика», а не отдельные слова: «link the nodes» и
# «download the PDF» — обычные шаги автоматизации, их пропускаем.
GIVEAWAY = r"(template|workflow|blueprint|code|json|prompt|guide|cheat ?sheet|file)s?"
PROMISE = re.compile("|".join([
    r"\blinks?\s+(is\s+|are\s+)?(in|below|down)\b",
    r"\b(in|under|check|see)\s+the\s+(video\s+)?description\b",
    r"\bdescription\s+(box|below)\b",
    r"\b(down|see|details|linked|listed|link|links|" + GIVEAWAY + r")\s+below\b",
    r"\b(below|under)\s+(the|this)\s+video\b",
    r"\b(show\s+notes|pinned\s+comment|first\s+comment)\b",
    r"\b(grab|get|download|steal)\s+(the|my|our|this|a)\s+(free\s+)?" + GIVEAWAY
    + r"\b(?!\s+(running|working|started|to\b))",
    r"\b" + GIVEAWAY + r"\s+(is|are)\s+(free|linked|below|available)\b",
]), re.IGNORECASE)
COMMENT_KEYWORD = re.compile(r"\b[Cc]omment\s+[\"“']?[A-Z]{3,}\b")  # «Comment TEMPLATE and I'll send it»


def promised_links(video: VideoScript) -> list[str]:
    """Фразы ролика (всё, что видит зритель), которые обещают ссылку, шаблон или загрузку."""
    texts = [video.title, video.description, video.thumbnail_text, *video.tags,
             *(scene.narration for scene in video.scenes)]
    return [match.group(0) for text in texts for pattern in (PROMISE, COMMENT_KEYWORD)
            for match in pattern.finditer(text)]


# Утверждения о результате автоматизации, которую никто не запускал (сверка роликов 3 и 4 15.11).
OVERCLAIM = re.compile("|".join([
    # «to never make up» — указание модели, а не утверждение о результате.
    r"(?<!\bto\s)\bnever\s+(be\s+)?(invent\w*|hallucinat\w*|miss\w*|fail\w*|forget\w*|drop\w*|break\w*"
    r"|makes?\s+up|made\s+up)\b",
    r"\bverified,?\s+(and\s+)?cited\b|\bverified\s+(\w+\s+)?(report|numbers|data|output)\b",
    r"\b(posts|runs|updates|sends|writes|fixes|maintains)\s+itself\b",
    r"\bguaranteed\b",
    r"\b100\s?(%|percent\b)\s*(accurate|reliable|correct|automated|of\s+the\s+time)",
    r"\bzero\s+(errors|mistakes|hallucinations)\b|\berror-free\b|\bflawless(ly)?\b",
    r"\b(always|perfectly|fully)\s+accurate\b",
    r"\b(routed|processed|classified|delivered|ready|done|arrives?|lands?|shows?\s+up)(\s+by\s+\w+)?\s+(in|within)\s+"
    r"(a\s+few\s+)?(seconds|minutes)\b|\binstantly\b",
    r"\bstays?\s+clean\b",
]), re.IGNORECASE)


# Ограничения Claude API, сверенные по документации 15.11.2026 (сверка ролика 5):
# - https://platform.claude.com/docs/en/models/sonnet-5-5/overview — «Setting `temperature`, `top_p`,
#   or `top_k` returns a 400 error.»
# - https://platform.claude.com/docs/en/api/errors — Opus 5.5, Sonnet 5.5, Fable 5.2/5.1, Mythos 5.2/5.1
#   «don't support forced tool use»: tool_choice any/tool → 400; auto и none принимаются.
# - https://platform.claude.com/docs/en/agents-and-tools/tool-use/strict-tool-use — без strict «Claude might
#   return incompatible types ... or omit required fields»; strict: true гарантирует соответствие схеме.
# - https://platform.claude.com/docs/en/build-with-claude/structured-outputs — «guarantee schema-compliant
#   responses»; в supportedModels есть claude-opus-5-5 и claude-sonnet-5-5.
# Пересматривать при выходе новых моделей.
API_FACTS = """When a video uses the Claude API, follow these facts from Anthropic's documentation:
- Do not tell viewers to set temperature, top_p or top_k: on Claude Sonnet 5.5 setting any of them returns \
a 400 error.
- Do not tell viewers to force a tool with tool_choice ("any" or a named tool): Claude Opus 5.5, Sonnet 5.5 \
and Fable 5.2 reject it with a 400 error. For structured data, use structured outputs (a JSON schema \
response format) or a tool defined with strict: true, then still validate the result in code.
- Without strict mode a tool call can have wrong types or missing required fields; do not say the \
arguments always match the schema unless strict mode or structured outputs are used."""

# Совет, который по документации выше даёт 400 на текущих моделях. Сценарий с ним не собирается.
API_ERROR = re.compile("|".join([
    r"\b(temperature|top[_ ]p|top[_ ]k)\b",
    r"\btool[_ ]choice\b",
    r"\bforc\w*\s+(\w+\s+){0,3}tool\b",
    r"\btool\s+(\w+\s+){0,2}forced\b",
]), re.IGNORECASE)

# Предметы, на которых модель картинок рисует мусорные буквы (ролик 5: кадры 1, 2, 4, 5, 6).
TEXTY_VISUAL = re.compile(
    r"\b(paper|papers|document|documents|invoice|invoices|receipt|receipts|book|books|page|pages|"
    r"screen|screens|monitor|monitors|code|spreadsheet|spreadsheets|chart|charts|dashboard|dashboards|"
    r"sign|signs|label|labels|database|newspaper|whiteboard)\b", re.IGNORECASE)


def api_errors(video: VideoScript) -> list[str]:
    texts = [video.title, video.description, video.thumbnail_text,
             *(scene.narration for scene in video.scenes)]
    return [match.group(0) for text in texts for match in API_ERROR.finditer(text)]


def texty_visuals(video: VideoScript) -> list[str]:
    return [f"сцена {i}: {match.group(0)}" for i, scene in enumerate(video.scenes, 1)
            for match in [TEXTY_VISUAL.search(scene.visual_prompt)] if match]


def overclaims(video: VideoScript) -> list[str]:
    texts = [video.title, video.description, video.thumbnail_text, *video.tags,
             *(scene.narration for scene in video.scenes)]
    return [match.group(0) for text in texts for match in OVERCLAIM.finditer(text)]


def page_is_live(url: str) -> bool:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 content-factory-check"}), timeout=15) as response:
            return response.status == 200
    except (OSError, ValueError, http.client.HTTPException):  # оборванный ответ = страница не жива
        return False


def check_promises(video: VideoScript) -> None:
    """Сценарий, обещающий ссылку, шаблон или код, собирается, только если в описании будет
    ссылка (PRODUCT_URL) и страница по ней жива. Иначе ролик встанет уже оплаченным."""
    claims = overclaims(video)
    if claims:
        raise RuntimeError(f"сценарий утверждает непроверенный результат: {', '.join(claims)}")
    errors = api_errors(video)
    if errors:
        raise RuntimeError(f"сценарий советует то, что Claude API отклоняет: {', '.join(errors)}")
    texty = texty_visuals(video)
    if texty:
        raise RuntimeError(f"картинка сцены нарисует мусорный текст: {', '.join(texty)}")
    promises = promised_links(video)
    if not promises:
        return
    if not config.PRODUCT_URL:
        raise RuntimeError(f"сценарий обещает ссылку, а PRODUCT_URL не задан: {', '.join(promises)}")
    if not page_is_live(config.PRODUCT_URL):
        raise RuntimeError(f"сценарий обещает ссылку, а {config.PRODUCT_URL} не отвечает 200: {', '.join(promises)}")


def system_prompt() -> str:
    ending = ENDING_WITH_LINK if config.PRODUCT_URL else ENDING_WITHOUT_LINK
    return SYSTEM.format(channel=config.CHANNEL_NAME, ending=ending, api_facts=API_FACTS)


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
        "Here is the result, what it costs to run, and what to try next.",
    ]
    return VideoScript(
        title=f"[DRY RUN] {topic}"[:70],
        description="Dry run. No API calls were made.",
        tags=["dry-run"],
        thumbnail_text="DRY RUN",
        scenes=[Scene(narration=t, visual_prompt=f"placeholder shot {i + 1}") for i, t in enumerate(lines)],
    )
