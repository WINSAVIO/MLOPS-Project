# ─────────────────────────────────────────────────────────────────────────────
# GridSight — Production Dockerfile
# Optimised for Google Cloud Run (ephemeral, stateless, minimal image)
# ─────────────────────────────────────────────────────────────────────────────

# Stage 1: slim Python base
FROM python:3.11-slim

# Prevents Python from writing .pyc files
ENV PYTHONDONTWRITEBYTECODE=1
# Prevents Python from buffering stdout/stderr (important for Cloud Run logs)
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# System deps — libgomp1 is required by XGBoost
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy and install ONLY the server dependencies (lean image)
COPY Interface/server/requirements-server.txt .
RUN pip install --no-cache-dir -r requirements-server.txt

# Copy backend server code
COPY Interface/server/ /app/

# Copy model artifacts (inference-only weights, no training data)
COPY ["Model Weights/", "/app/Model Weights/"]

# Cloud Run requires the container to listen on $PORT (default 8080)
ENV PORT=8080
EXPOSE 8080

# Non-root user for security
RUN adduser --disabled-password --gecos "" appuser
USER appuser

# Start the server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
