# Production-oriented image: Gunicorn + WhiteNoise static; optional TensorFlow for ML training/inference.
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=matika.settings

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/staticfiles /app/media

EXPOSE 8000

# Default: override in docker-compose (migrate + collectstatic + gunicorn)
CMD ["gunicorn", "matika.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "120"]
