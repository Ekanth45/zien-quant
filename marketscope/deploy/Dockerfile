FROM python:3.12-slim

WORKDIR /app

# Install security updates
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    curl && rm -rf /var/lib/apt/lists/*

COPY requirements-live.txt .
RUN pip install --no-cache-dir -r requirements-live.txt || true

COPY . .

# Run as non-root user
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/work/runtime /app/work/backups && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8765

CMD ["python", "server.py", "--host", "0.0.0.0", "--port", "8765"]
