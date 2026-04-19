FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.railway.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir yt-dlp

COPY backend/ .

RUN mkdir -p /tmp/uploads /tmp/processing

EXPOSE 8000
