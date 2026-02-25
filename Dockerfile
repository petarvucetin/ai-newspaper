FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/
COPY scripts/ ./scripts/
COPY config.yaml .

# Create data directory for SQLite DB
RUN mkdir -p /app/data

# Expose port
EXPOSE 8000

# Initialize DB then start server
CMD ["sh", "-c", "python3 scripts/init_db.py && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
