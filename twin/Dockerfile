FROM python:3.11-slim-bookworm

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

EXPOSE 5000
EXPOSE 8050

CMD ["python", "app/dashboard.py"]
