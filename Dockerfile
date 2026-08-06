FROM python:3.11-slim

# ffmpeg is needed by the render pipeline; node is needed to invoke the
# Remotion render-engine as a subprocess from this service. The long apt
# list below is Chrome/Chromium's runtime dependencies, required for
# Remotion's headless browser renderer to launch.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg curl gnupg \
        libnspr4 libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
        libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 \
        libxrandr2 libgbm1 libasound2 libpango-1.0-0 libcairo2 \
        libatspi2.0-0 libx11-6 libxext6 libxcb1 \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# NOTE: build this image with the REPO ROOT as build context (see
# docker-compose.yml / railway.json), so we can pull in render-engine too:
#   docker build -f backend/Dockerfile .
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
COPY render-engine/ /app/render-engine
RUN cd /app/render-engine && npm install

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
