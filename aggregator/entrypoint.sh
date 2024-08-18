#!/bin/bash
set -e

echo "Current working directory:"
pwd
echo "Contents of current directory:"
ls -la
echo "Contents of agents directory:"
ls -la /app/agents

if [ "$1" = "aggregator" ]; then
    echo "Starting aggregator..."
    exec gunicorn --bind 0.0.0.0:5000 app:app
elif [ "$1" = "celery" ]; then
    echo "Starting Celery worker..."
    exec celery -A app.celery worker --loglevel=info
else
    exec "$@"
fi