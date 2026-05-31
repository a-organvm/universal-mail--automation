FROM python:3.11-slim

WORKDIR /app

# Install deps first for layer caching.
COPY requirements.txt requirements-api.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-api.txt

COPY . .

EXPOSE 8000

# Provider credentials are supplied at runtime via environment (see CLAUDE.md).
CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000"]
