#!/bin/bash

# Build aggregator image
docker build -t your-registry/aggregator:latest ./aggregator

# Build agents image
docker build -t your-registry/agents:latest ./agents

# Build frontend image
docker build -t your-registry/frontend:latest ./frontend

# Push images to registry
docker push your-registry/aggregator:latest
docker push your-registry/agents:latest
docker push your-registry/frontend:latest

echo "All images have been built and pushed to the registry."