# eidosSpeech v2 - Dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies (curl for healthcheck, ffmpeg for audio processing)
RUN apt-get update && apt-get install -y curl ffmpeg && rm -rf /var/lib/apt/lists/*

# Copy requirements and install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app ./app
COPY cleanup_duplicates.py .
COPY run_migrations.py .
COPY entrypoint.sh .
COPY .env.example .

# Create data directories
RUN mkdir -p /app/data/db /app/data/cache

# Make entrypoint executable
RUN chmod +x entrypoint.sh

# Create non-root user
RUN useradd -m eidos && chown -R eidos:eidos /app
USER eidos

# Environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8001

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8001/api/v1/health || exit 1

# Run command
CMD ["./entrypoint.sh"]
