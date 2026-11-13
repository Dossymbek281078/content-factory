"""Озвучка (ElevenLabs) и визуал (Replicate) для одной сцены, плюс заглушки для --dry-run."""

import subprocess
import time
from pathlib import Path

import requests

from . import config


def run_ffmpeg(args: list[str]) -> None:
    proc = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg завершился с ошибкой:\n{proc.stderr.strip()[-2000:]}")


def duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


# --- Озвучка ---------------------------------------------------------------

def voice(text: str, out: Path) -> Path:
    response = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{config.ELEVENLABS_VOICE_ID}",
        headers={"xi-api-key": config.require("ELEVENLABS_API_KEY"), "Accept": "audio/mpeg"},
        json={
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        },
        timeout=120,
    )
    if not response.ok:
        raise RuntimeError(f"ElevenLabs вернул {response.status_code}: {response.text[:300]}")
    out.write_bytes(response.content)
    return out


def mock_voice(text: str, out: Path) -> Path:
    seconds = max(2.0, len(text.split()) / 2.5)  # ~150 слов в минуту
    run_ffmpeg(["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", f"{seconds:.2f}",
                "-c:a", "libmp3lame", str(out)])
    return out


# --- Визуал ----------------------------------------------------------------

def visual(prompt: str, out_stem: Path) -> Path:
    """Возвращает путь к картинке (.png) или клипу (.mp4) в зависимости от VISUAL_MODE."""
    # Обычный HTTP вместо клиента replicate: тот ходит в сеть мимо системного прокси.
    headers = {"Authorization": f"Bearer {config.require('REPLICATE_API_TOKEN')}"}
    if config.VISUAL_MODE == "video":
        model, params, suffix = config.REPLICATE_VIDEO_MODEL, {"prompt": prompt}, ".mp4"
    else:
        model = config.REPLICATE_IMAGE_MODEL
        params = {"prompt": prompt, "aspect_ratio": "16:9", "output_format": "png"}
        suffix = ".png"

    response = requests.post(
        f"https://api.replicate.com/v1/models/{model}/predictions",
        headers={**headers, "Prefer": "wait"}, json={"input": params}, timeout=120,
    )
    if not response.ok:
        raise RuntimeError(f"Replicate вернул {response.status_code}: {response.text[:300]}")
    prediction = response.json()
    deadline = time.monotonic() + 900
    while prediction["status"] in ("starting", "processing"):
        if time.monotonic() > deadline:
            raise RuntimeError(f"Replicate не закончил генерацию за 15 минут ({prediction['id']})")
        time.sleep(3)
        poll = requests.get(prediction["urls"]["get"], headers=headers, timeout=60)
        poll.raise_for_status()
        prediction = poll.json()
    if prediction["status"] != "succeeded":
        raise RuntimeError(f"Replicate: {prediction['status']}: {prediction.get('error')}")

    output = prediction["output"]
    url = output[0] if isinstance(output, list) else output
    download = requests.get(url, timeout=300)
    download.raise_for_status()
    out = out_stem.with_suffix(suffix)
    out.write_bytes(download.content)
    return out


def mock_visual(index: int, out_stem: Path) -> Path:
    colors = ["0x1f3a5f", "0x2d6a4f", "0x6a2d4f", "0x5f4b1f", "0x3d3d6b"]
    out = out_stem.with_suffix(".png")
    run_ffmpeg(["-f", "lavfi",
                "-i", f"color=c={colors[index % len(colors)]}:s={config.WIDTH}x{config.HEIGHT}",
                "-vf", f"drawtext=text='Scene {index + 1}':fontcolor=white:fontsize=120:"
                       "x=(w-text_w)/2:y=(h-text_h)/2",
                "-frames:v", "1", str(out)])
    return out
