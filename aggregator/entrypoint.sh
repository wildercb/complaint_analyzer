#!/bin/bash
set -e

echo "Current working directory:"
pwd
echo "Contents of current directory:"
ls -la

if [ "$1" = "aggregator" ]; then
    echo "Starting aggregator..."
    exec gunicorn --bind 0.0.0.0:5000 \
              --workers 2 \
              --threads 4 \
              --worker-class gthread \
              --timeout 300 \
              --keep-alive 5 \
              --max-requests 1000 \
              --max-requests-jitter 50 \
              --log-level debug \
              app:app
elif [ "$1" = "worker" ]; then
    echo "Starting RQ worker..."
    exec rq worker --url redis://redis:6379/0
else
    exec "$@"
fi