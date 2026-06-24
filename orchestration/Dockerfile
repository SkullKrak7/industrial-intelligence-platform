FROM python:3.11-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

# Build context is the repo root (see docker-compose.yml)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

COPY orchestration/ /app/orchestration/
COPY dbt/ /app/dbt/
COPY pipeline/ /app/pipeline/

CMD ["dagster", "dev", "-f", "/app/orchestration/dagster_pipeline.py", \
     "--host", "0.0.0.0", "--port", "3000"]
