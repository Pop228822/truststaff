# БАЗА: bookworm, чтобы был wkhtmltopdf из apt
FROM python:3.11-bookworm

# Не задавай интерактивные переменные для apt
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Системные пакеты + wkhtmltopdf + шрифты для кириллицы/Unicode
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    wkhtmltopdf \
    fonts-dejavu-core fonts-noto fonts-noto-cjk \
 && apt-get clean && rm -rf /var/lib/apt/lists/*

# Рабочая директория
WORKDIR /app

# Сначала зависимости — чтобы кешировались слои
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# Потом код
COPY . .

# (опционально) создадим непривилегированного пользователя
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Порт приложения
EXPOSE 8000

# Healthcheck (по желанию — укажи свой маршрут, например /health)
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
 CMD curl -fsS http://127.0.0.1:8000/health || exit 1

# Запуск uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--log-level", "debug"]