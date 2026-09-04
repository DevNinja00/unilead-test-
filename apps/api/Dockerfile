FROM python:3.12-slim AS base

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential && \
    rm -rf /var/lib/apt/lists/*

# Python deps
COPY apps/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy AI education library
COPY services/ai_education /app/services/ai_education

# Copy API app
COPY apps/api /app/apps/api

WORKDIR /app/apps/api

EXPOSE 8000

CMD ["python", "-m", "app.main"]
