FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdrm2 libdbus-1-3 libxkbcommon0 libatspi2.0-0 libxcomposite1 \
    libxdamage1 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 \
    libcairo2 libasound2 libwayland-client0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
COPY api/requirements.txt api/
RUN pip install --no-cache-dir -r requirements.txt -r api/requirements.txt

RUN playwright install chromium

COPY . .

EXPOSE 8000

CMD sh -c "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"
