"""Загрузка готового ролика на YouTube со своего компьютера. Ролик уходит приватным.

    pip install google-auth-oauthlib google-api-python-client
    python upload_local.py client_secret.json final.mp4 script.json

При первом запуске откроется браузер для входа; токен сохранится рядом в youtube_token.json,
и дальше вход не потребуется. Файлы client_secret.json и youtube_token.json никому не передавайте.
"""

import json
import sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
TOKEN = Path("youtube_token.json")


def credentials(client_secret: str) -> Credentials:
    creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES) if TOKEN.exists() else None
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(client_secret, SCOPES)
        creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
    TOKEN.write_text(creds.to_json(), encoding="utf-8")
    return creds


def main() -> None:
    if len(sys.argv) != 4:
        sys.exit("Запуск: python upload_local.py client_secret.json final.mp4 script.json")
    client_secret, video, script_file = sys.argv[1:]
    script = json.loads(Path(script_file).read_text(encoding="utf-8"))

    request = build("youtube", "v3", credentials=credentials(client_secret)).videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": script["title"][:100],
                "description": script["description"],
                "tags": script["tags"][:30],
                "categoryId": "28",
            },
            "status": {
                "privacyStatus": "private",
                "selfDeclaredMadeForKids": False,
                "containsSyntheticMedia": True,
            },
        },
        media_body=MediaFileUpload(video, chunksize=8 * 1024 * 1024, resumable=True),
    )
    response = None
    while response is None:
        progress, response = request.next_chunk()
        if progress:
            print(f"загружено {int(progress.progress() * 100)}%")
    print(f"Готово, ролик приватный: https://studio.youtube.com/video/{response['id']}/edit")


if __name__ == "__main__":
    main()
