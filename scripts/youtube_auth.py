"""Разовое получение YOUTUBE_REFRESH_TOKEN. Запускать на своём компьютере, не на сервере.

1. Google Cloud Console -> включить YouTube Data API v3 -> создать OAuth client типа "Desktop app".
2. Скачать client_secret.json в эту папку.
3. python scripts/youtube_auth.py client_secret.json
4. Войти под аккаунтом канала; три значения из вывода перенести в .env / Railway Variables.
"""

import sys

from google_auth_oauthlib.flow import InstalledAppFlow

flow = InstalledAppFlow.from_client_secrets_file(
    sys.argv[1], ["https://www.googleapis.com/auth/youtube.upload"]
)
credentials = flow.run_local_server(port=0, access_type="offline", prompt="consent")
print(f"YOUTUBE_CLIENT_ID={credentials.client_id}")
print(f"YOUTUBE_CLIENT_SECRET={credentials.client_secret}")
print(f"YOUTUBE_REFRESH_TOKEN={credentials.refresh_token}")
