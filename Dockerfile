FROM python:3.11-slim

WORKDIR /app

# Install deps first for layer caching.
COPY requirements.txt requirements-api.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-api.txt

COPY . .

EXPOSE 8000

# Provider credentials are supplied at runtime via environment (see CLAUDE.md).
# Shell form so a platform-provided $PORT (Render/Fly/Cloud Run) is honored,
# defaulting to 8000 for local `docker run -p 8000:8000`.
CMD uvicorn api.app:app --host 0.0.0.0 --port ${PORT:-8000}
