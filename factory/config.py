import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def require(name: str) -> str:
    value = env(name)
    if not value:
        raise RuntimeError(f"Не задана переменная окружения {name} (см. .env.example)")
    return value


DATA_DIR = Path(env("DATA_DIR", "data"))
CHANNEL_NAME = env("CHANNEL_NAME", "AI Automation Lab")
PRODUCT_URL = env("PRODUCT_URL")

# Боевой проект Railway. Любой другой проект на том же репозитории (15.11 так платно собрал
# ролики 1–5 лишний mellow-rebirth) не собирает и не загружает. Вне Railway проверки нет.
# Константа, а не переменная окружения: скопированные переменные не должны отключать проверку.
# Пересоздали боевой проект — поменять здесь (railway variables: RAILWAY_PROJECT_ID).
HOME_RAILWAY_PROJECT_ID = "ece53425-176c-4f19-a925-12f8f43ce103"


def foreign_railway_project() -> str:
    """Имя чужого проекта Railway, если запущены в нём; иначе пустая строка."""
    current = env("RAILWAY_PROJECT_ID")
    if current and current != HOME_RAILWAY_PROJECT_ID:
        return env("RAILWAY_PROJECT_NAME") or current
    return ""


VISUAL_MODE = env("VISUAL_MODE", "image")
REPLICATE_IMAGE_MODEL = env("REPLICATE_IMAGE_MODEL", "black-forest-labs/flux-schnell")
REPLICATE_VIDEO_MODEL = env("REPLICATE_VIDEO_MODEL", "minimax/video-01")
ELEVENLABS_VOICE_ID = env("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")

WIDTH, HEIGHT, FPS = 1920, 1080, 30
