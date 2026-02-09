FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd -m -u 1000 agentuser && \
    mkdir -p /app/logs && \
    chown -R agentuser:agentuser /app && \
    chmod -R 755 /app && \
    chmod -R 777 /app/logs

USER agentuser

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

ENTRYPOINT ["python3", "-m", "src.cli"]
CMD ["--help"]