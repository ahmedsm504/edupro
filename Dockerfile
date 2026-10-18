FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends build-essential libpq-dev && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# ملفات الـ CSS/JS بتتجمع وقت البناء (whitenoise بيقدّمها)
RUN DEBUG=False SECRET_KEY=build-only python manage.py collectstatic --noinput
EXPOSE 8000
# Railway بيدّي البورت في $PORT
CMD ["sh", "-c", "daphne -b 0.0.0.0 -p ${PORT:-8000} config.asgi:application"]
