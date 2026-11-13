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

VISUAL_MODE = env("VISUAL_MODE", "image")
REPLICATE_IMAGE_MODEL = env("REPLICATE_IMAGE_MODEL", "black-forest-labs/flux-schnell")
REPLICATE_VIDEO_MODEL = env("REPLICATE_VIDEO_MODEL", "minimax/video-01")
ELEVENLABS_VOICE_ID = env("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")

WIDTH, HEIGHT, FPS = 1920, 1080, 30
