# Use Python base image
FROM python:3.11-slim

# Install system dependencies for Playwright
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
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Install Playwright
RUN pip install --no-cache-dir playwright flask beautifulsoup4
RUN playwright install chromium

# Set workdir
WORKDIR /app

# Copy app files
COPY . .

# Expose Flask port
EXPOSE 8080

# Run Flask
CMD ["python", "app.py"]
