"""CLI конвейера.

  python -m factory add "тема ролика"
  python -m factory run [--limit N] [--dry-run] [--upload]
  python -m factory list
  python -m factory upload ID
"""

import argparse
import sys
from pathlib import Path

from . import assemble, config, media, store
from .models import VideoScript
from .script import generate_script, mock_script


def render(row, dry_run: bool) -> tuple[VideoScript, Path]:
    work = config.DATA_DIR / f"video_{row['id']:04}"
    work.mkdir(parents=True, exist_ok=True)

    # Готовый сценарий и готовые файлы сцен переиспользуются: повторный запуск после сбоя
    # не платит второй раз за уже сгенерированное.
    script_file = work / "script.json"
    if script_file.exists():
        script = VideoScript.model_validate_json(script_file.read_text(encoding="utf-8"))
    else:
        script = mock_script(row["topic"]) if dry_run else generate_script(row["topic"])
        script_file.write_text(script.model_dump_json(indent=2), encoding="utf-8")

    clips, durations = [], []
    for i, scene in enumerate(script.scenes):
        print(f"  сцена {i + 1}/{len(script.scenes)}", flush=True)
        audio = work / f"scene_{i:02}.mp3"
        if not audio.exists():
            (media.mock_voice if dry_run else media.voice)(scene.narration, audio)
        stem = work / f"scene_{i:02}_visual"
        visual = next((p for p in (stem.with_suffix(".png"), stem.with_suffix(".mp4")) if p.exists()), None)
        if visual is None:
            visual = media.mock_visual(i, stem) if dry_run else media.visual(scene.visual_prompt, stem)
        clip = work / f"scene_{i:02}.mp4"
        durations.append(assemble.render_scene(visual, audio, clip))
        clips.append(clip)

    srt = assemble.write_srt([s.narration for s in script.scenes], durations, work / "captions.srt")
    final = assemble.concat_with_captions(clips, srt, work / "final.mp4")
    return script, final


def sync_topics(db) -> None:
    """Добавляет в очередь новые строки из topics.txt (по теме на строку, # — комментарий)."""
    topics_file = Path("topics.txt")
    if not topics_file.exists():
        return
    known = {row["topic"] for row in store.everything(db)}
    for line in topics_file.read_text(encoding="utf-8").splitlines():
        topic = line.strip()
        if topic and not topic.startswith("#") and topic not in known:
            known.add(topic)
            print(f"новая тема [{store.add(db, topic)}]: {topic}")


def upload(db, row) -> None:
    from .youtube import upload_private

    youtube_id = upload_private(Path(row["video_path"]), VideoScript.model_validate_json(row["script_json"]))
    store.update(db, row["id"], status="uploaded", youtube_id=youtube_id)
    print(f"  загружен приватным: https://studio.youtube.com/video/{youtube_id}/edit")


def cmd_run(args) -> int:
    db = store.connect()
    sync_topics(db)
    failed = 0
    for row in store.by_status(db, "queued", args.limit):
        print(f"[{row['id']}] {row['topic']}", flush=True)
        try:
            script, final = render(row, args.dry_run)
        except Exception as error:  # один сбойный ролик не должен останавливать очередь
            store.update(db, row["id"], status="failed", error=str(error))
            print(f"  ОШИБКА: {error}", file=sys.stderr)
            failed += 1
            continue
        store.update(db, row["id"], status="rendered", script_json=script.model_dump_json(),
                     video_path=str(final), error=None)
        print(f"  готово: {final} ({media.duration(final):.0f} с)")

    if args.upload:
        # Включает ролики, собранные в прошлых запусках, чья загрузка тогда не удалась.
        for row in store.by_status(db, "rendered"):
            print(f"[{row['id']}] загрузка на YouTube", flush=True)
            try:
                upload(db, row)
            except Exception as error:
                print(f"  ОШИБКА загрузки: {error}", file=sys.stderr)
                failed += 1
    return 1 if failed else 0


def cmd_upload(args) -> int:
    db = store.connect()
    row = store.get(db, args.id)
    if row is None or row["status"] != "rendered":
        print("Загрузить можно только ролик в статусе rendered (см. `list`).", file=sys.stderr)
        return 1
    upload(db, row)
    return 0


def cmd_add(args) -> int:
    print(f"В очереди под номером {store.add(store.connect(), args.topic)}")
    return 0


def cmd_list(args) -> int:
    for row in store.everything(store.connect()):
        extra = row["youtube_id"] or row["error"] or row["video_path"] or ""
        print(f"{row['id']:>4}  {row['status']:<9} {row['topic'][:60]:<60} {extra[:80]}")
    return 0


def cmd_retry(args) -> int:
    db = store.connect()
    for row in store.by_status(db, "failed"):
        store.update(db, row["id"], status="queued", error=None)
        print(f"[{row['id']}] возвращён в очередь")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="factory")
    sub = parser.add_subparsers(required=True)
    p = sub.add_parser("add", help="добавить тему в очередь"); p.add_argument("topic"); p.set_defaults(fn=cmd_add)
    p = sub.add_parser("run", help="собрать ролики из очереди")
    p.add_argument("--limit", type=int); p.add_argument("--dry-run", action="store_true",
                                                         help="без обращений к API: заглушки вместо голоса и картинки")
    p.add_argument("--upload", action="store_true", help="сразу загрузить готовые ролики на YouTube приватными")
    p.set_defaults(fn=cmd_run)
    p = sub.add_parser("list", help="показать очередь"); p.set_defaults(fn=cmd_list)
    p = sub.add_parser("retry", help="вернуть упавшие ролики в очередь"); p.set_defaults(fn=cmd_retry)
    p = sub.add_parser("upload", help="загрузить готовый ролик на YouTube приватным")
    p.add_argument("id", type=int); p.set_defaults(fn=cmd_upload)
    args = parser.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
