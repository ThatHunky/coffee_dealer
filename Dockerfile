# Use Python 3.12 slim image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies including emoji font
RUN apt-get update && apt-get install -y \
    fonts-dejavu-core \
    fonts-dejavu \
    fonts-noto-color-emoji \
    fonts-symbola \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY fonts/ ./fonts/
COPY .env.example .env.example

# Create directory for database
RUN mkdir -p /app/data

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV DATABASE_URL=sqlite:///./data/schedule.db

# Run the bot
CMD ["python", "-m", "src.main"]
