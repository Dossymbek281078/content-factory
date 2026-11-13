"""Сборка: сцены -> клипы под длину озвучки -> склейка -> вшитые субтитры."""

import re
from pathlib import Path

from . import config
from .media import duration, run_ffmpeg

W, H, FPS = config.WIDTH, config.HEIGHT, config.FPS
FILL = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}"


def render_scene(visual: Path, audio: Path, out: Path) -> float:
    """Собирает клип сцены длиной ровно в её озвучку. Возвращает длительность в секундах."""
    seconds = duration(audio)
    if visual.suffix == ".mp4":
        video_in = ["-stream_loop", "-1", "-i", str(visual)]
        vf = f"{FILL},fps={FPS}"
    else:
        # Плавный наезд на статичную картинку; увеличение исходника убирает дрожание zoompan.
        frames = int(seconds * FPS) + 1
        video_in = ["-i", str(visual)]
        vf = (f"scale={W * 2}:{H * 2}:force_original_aspect_ratio=increase,crop={W * 2}:{H * 2},"
              f"zoompan=z='min(1+0.10*on/{frames},1.10)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
              f":d={frames}:s={W}x{H}:fps={FPS}")
    run_ffmpeg([*video_in, "-i", str(audio), "-vf", vf, "-map", "0:v:0", "-map", "1:a:0",
                "-t", f"{seconds:.3f}", "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2", str(out)])
    return duration(out)


def _chunks(text: str, max_words: int = 7) -> list[str]:
    result = []
    for sentence in re.split(r"(?<=[.!?])\s+", text.strip()):
        words = sentence.split()
        result += [" ".join(words[i:i + max_words]) for i in range(0, len(words), max_words)]
    return [c for c in result if c]


def _timestamp(seconds: float) -> str:
    ms = round(seconds * 1000)
    return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"


def write_srt(narrations: list[str], durations: list[float], out: Path) -> Path:
    """Субтитры: время внутри сцены делится между фразами пропорционально их длине."""
    entries, offset = [], 0.0
    for text, scene_seconds in zip(narrations, durations):
        chunks = _chunks(text)
        total_chars = sum(len(c) for c in chunks) or 1
        start = offset
        for chunk in chunks:
            end = start + scene_seconds * len(chunk) / total_chars
            entries.append(f"{len(entries) + 1}\n{_timestamp(start)} --> {_timestamp(end)}\n{chunk}\n")
            start = end
        offset += scene_seconds
    out.write_text("\n".join(entries), encoding="utf-8")
    return out


def concat_with_captions(clips: list[Path], srt: Path, out: Path) -> Path:
    listing = out.with_suffix(".txt")
    listing.write_text("".join(f"file '{c.resolve()}'\n" for c in clips), encoding="utf-8")
    style = "FontName=DejaVu Sans,FontSize=20,Outline=2,Shadow=0,MarginV=40"
    srt_arg = str(srt.resolve()).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
    run_ffmpeg(["-f", "concat", "-safe", "0", "-i", str(listing),
                "-vf", f"subtitles='{srt_arg}':force_style='{style}'",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                "-c:a", "copy", "-movflags", "+faststart", str(out)])
    listing.unlink()
    return out
