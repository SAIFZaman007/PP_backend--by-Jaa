# ---- Peak Physique backend image ----
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Install uv (fast, reproducible dependency management)
RUN pip install --no-cache-dir uv

WORKDIR /app

# Install deps first for better layer caching
COPY pyproject.toml ./
RUN uv pip install --system -r pyproject.toml

# App source
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]