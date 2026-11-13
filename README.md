# Content Factory

Конвейер черновиков для YouTube-канала: тема → сценарий (Claude) → озвучка по сценам (ElevenLabs)
→ картинка или клип на каждую сцену (Replicate) → сборка с субтитрами (FFmpeg) → загрузка на
YouTube **приватным** роликом. Публикует человек после просмотра.

## Запуск

```bash
pip install -r requirements.txt
```

```bash
cp .env.example .env
```

```bash
python -m factory add "How to auto-triage support email with Claude and Supabase"
```

```bash
python -m factory run --dry-run
```

`--dry-run` собирает ролик на заглушках без обращений к API и без расходов. Без флага нужны ключи
из `.env.example`. Нужен установленный `ffmpeg`.

| Команда | Что делает |
|---|---|
| `add "тема"` | ставит тему в очередь |
| `run [--limit N] [--upload]` | собирает ролики из очереди в `data/video_NNNN/final.mp4`; с `--upload` сразу грузит их приватными |
| `list` | показывает очередь и статусы |
| `retry` | возвращает упавшие ролики в очередь (готовые сцены не генерируются заново) |
| `upload ID` | загружает готовый ролик на YouTube приватным |

## Настройки

- `VISUAL_MODE=image` — картинка на сцену с плавным наездом, доли цента за сцену.
  `VISUAL_MODE=video` — видеоклип на сцену, на порядки дороже.
- Имена моделей Replicate задаются в `.env`; перед первым запуском сверьте их с каталогом Replicate.
- Refresh token для YouTube: `python scripts/youtube_auth.py client_secret.json` на своём компьютере.

## Деплой на Railway

1. Сервис из GitHub-репозитория: Railway сам соберёт `Dockerfile`.
2. **Variables:** все переменные из `.env.example` и `DATA_DIR=/app/data`.
3. **Volume** с точкой монтирования `/app/data`: без него очередь теряется при каждом запуске
   и ролики собираются повторно.
4. **Settings → Cron Schedule**, например `0 14 * * *` (раз в день, время в UTC).

Каждый запуск добавляет в очередь новые строки из `topics.txt`, собирает один ролик, загружает его
на YouTube приватным и завершается. Новые темы добавляются правкой `topics.txt` в репозитории.
Публикует ролик человек после просмотра в YouTube Studio.
