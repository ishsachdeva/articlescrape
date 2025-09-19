# Use Python base image
FROM python:3.11-slim

# Install system dependencies for Playwright + Chromium
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    libnss3 \
    libxss1 \
    libasound2 \
    fonts-liberation \
    fonts-unifont \
    fonts-dejavu \
    libgtk-3-0 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libxshmfence1 \
    libx11-dev \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install --with-deps chromium

# Set workdir
WORKDIR /app

# Copy app files
COPY . .

# Expose Flask/Gunicorn port
EXPOSE 8080

# Run with gunicorn for production
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:8080", "app:app"]
