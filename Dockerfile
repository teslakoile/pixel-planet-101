# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install API-specific dependencies
RUN pip install --no-cache-dir \
    fastapi==0.109.0 \
    uvicorn[standard]==0.27.0 \
    pydantic==2.5.3

# Copy application code
COPY src/ ./src/
COPY api_service.py .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Environment variables will be injected at runtime by Cloud Run
# Do not copy .env file - it contains secrets and should not be in the image

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run the API service
CMD exec uvicorn api_service:app --host 0.0.0.0 --port $PORT --workers 1

