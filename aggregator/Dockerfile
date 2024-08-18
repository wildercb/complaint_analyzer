FROM python:3.9-slim

WORKDIR /app

COPY aggregator/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY aggregator /app
COPY agents /app/agents
COPY aggregator/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV PYTHONPATH=/app

ENTRYPOINT ["/entrypoint.sh"]