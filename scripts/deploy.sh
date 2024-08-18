#!/bin/bash

# Apply Kubernetes configurations
kubectl apply -f kubernetes/

# Wait for deployments to be ready
kubectl rollout status deployment/aggregator
kubectl rollout status deployment/agents
kubectl rollout status deployment/frontend
kubectl rollout status statefulset/postgres

echo "All deployments have been applied and are ready."

# Get the external IP of the ingress
EXTERNAL_IP=$(kubectl get ingress complaint-analysis-ingress -o jsonpath='{.status.loadBalancer.ingress[0].ip}')

echo "Application is accessible at: http://$EXTERNAL_IP"