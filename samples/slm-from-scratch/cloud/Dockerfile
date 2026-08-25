# Production Multi-Stage Dockerfile for Serving SLM on Google Cloud Run
FROM python:3.11-slim

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8080
ENV ARTIFACTS_DIR=/app/artifacts

WORKDIR /app

# Install minimal system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and trained artifacts
COPY slm/ /app/slm/
COPY cloud/ /app/cloud/
COPY artifacts/ /app/artifacts/

# Create non-root user for security best practices
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

# Healthcheck for Cloud Run container lifecycle
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Start FastAPI serving process
CMD ["uvicorn", "cloud.app:app", "--host", "0.0.0.0", "--port", "8080"]
