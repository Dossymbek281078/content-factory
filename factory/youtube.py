"""Загрузка на YouTube. Ролик всегда уходит приватным: публикует человек после просмотра."""

from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from . import config
from .models import VideoScript

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def upload_private(video: Path, script: VideoScript) -> str:
    credentials = Credentials(
        token=None,
        refresh_token=config.require("YOUTUBE_REFRESH_TOKEN"),
        client_id=config.require("YOUTUBE_CLIENT_ID"),
        client_secret=config.require("YOUTUBE_CLIENT_SECRET"),
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES,
    )
    description = script.description
    if config.PRODUCT_URL:
        description = f"Template and code: {config.PRODUCT_URL}\n\n{description}"

    request = build("youtube", "v3", credentials=credentials).videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": script.title[:100],
                "description": description,
                "tags": script.tags[:30],
                "categoryId": "28",  # Science & Technology
            },
            "status": {
                "privacyStatus": "private",
                "selfDeclaredMadeForKids": False,
                # Обязательная пометка YouTube для синтетического голоса и картинки.
                "containsSyntheticMedia": True,
            },
        },
        media_body=MediaFileUpload(str(video), chunksize=8 * 1024 * 1024, resumable=True),
    )
    response = None
    while response is None:
        _, response = request.next_chunk()
    return response["id"]
