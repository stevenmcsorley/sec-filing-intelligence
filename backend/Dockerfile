FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend/requirements.txt backend/requirements-dev.txt ./
# Ensure system build dependencies are present for packages that require compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libpq-dev \
    cargo \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip/setuptools/wheel to ensure modern wheel support
RUN python -m pip install --upgrade pip setuptools wheel

# Install Python requirements (no-cache-dir to keep image small)
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./
COPY backend/scripts ./scripts
COPY backend/docker-entrypoint.sh ./

RUN chmod +x docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
