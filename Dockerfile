FROM python:3.13-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY factory ./factory
COPY topics.txt .
# Собирает один ролик из очереди, загружает его приватным и завершается: запускайте по расписанию.
CMD ["python", "-m", "factory", "run", "--limit", "1", "--upload"]
