FROM python:3.11-slim

# ffmpeg is needed by the render pipeline; node is needed to invoke the
# Remotion render-engine as a subprocess from this service.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg curl gnupg \
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

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
