FROM python:3.11-slim

WORKDIR /app

# Install deps first for layer caching. The deploy image is Python 3.11, so it
# also installs requirements-mcp.txt (the `mcp` SDK needs >=3.10) — this is what
# lights up the hosted /mcp endpoint. The core stays 3.9-importable without it.
COPY requirements.txt requirements-api.txt requirements-mcp.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-api.txt \
    -r requirements-mcp.txt

COPY . .

EXPOSE 8000

# Provider credentials are supplied at runtime via environment (see CLAUDE.md).
# Shell form so a platform-provided $PORT (Render/Fly/Cloud Run) is honored,
# defaulting to 8000 for local `docker run -p 8000:8000`.
CMD uvicorn api.app:app --host 0.0.0.0 --port ${PORT:-8000}
