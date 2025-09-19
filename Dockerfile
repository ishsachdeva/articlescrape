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

# Install Python dependencies including playwright-stealth
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browser binaries
RUN playwright install --with-deps chromium

# Set workdir
WORKDIR /app

# Copy app files
COPY . .

# Expose Flask port
EXPOSE 8080

# Run the app with Gunicorn (more stable than flask dev server)
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "app:app"]
