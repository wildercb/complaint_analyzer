#!/bin/bash

# Create ConfigMap
kubectl create configmap complaint-analysis-config \
    --from-literal=POSTGRES_HOST=postgres-service \
    --from-literal=POSTGRES_DB=complaintsdb \
    --from-literal=ELASTICSEARCH_URL=http://elasticsearch-service:9200 \
    --from-literal=REDIS_HOST=redis-service \
    --from-literal=CELERY_BROKER_URL=redis://redis-service:6379/0 \
    --from-literal=FLASK_ENV=production

# Create Secret
kubectl create secret generic complaint-analysis-secrets \
    --from-literal=POSTGRES_USER=$POSTGRES_USER \
    --from-literal=POSTGRES_PASSWORD=$POSTGRES_PASSWORD \
    --from-literal=OPENAI_API_KEY=$OPENAI_API_KEY \
    --from-file=GOOGLE_APPLICATION_CREDENTIALS=$GOOGLE_APPLICATION_CREDENTIALS

echo "Environment variables have been set up in Kubernetes."