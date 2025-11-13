FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install LibreOffice (headless usage) and fonts for better PDF fidelity
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice-calc libreoffice-writer libreoffice-core libreoffice-common \
    fonts-dejavu fonts-liberation fonts-noto-cjk \
    ca-certificates curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy app source
COPY backend /app

EXPOSE 8000

# Explicit path to soffice in container
ENV LIBREOFFICE_PATH=/usr/bin/soffice

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

