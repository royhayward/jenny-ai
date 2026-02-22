FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY email_service/src/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY email_service/src/ ./src/

RUN mkdir -p /app/data

ENV DATA_DIR=/app/data
ENV MCP_PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["python", "src/server.py"]
