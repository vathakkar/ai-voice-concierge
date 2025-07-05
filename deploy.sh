#!/bin/bash
set -e

# Variables
ACR_NAME="aiconciergeregistry-eta2akbcfvfqfycd.azurecr.io"
IMAGE_NAME="ai-concierge"
APP_SERVICE="ai-voice-concierge"
RESOURCE_GROUP="ai-concierge"

# Build Docker image

echo "Building Docker image..."
docker buildx build --platform linux/amd64 -t $IMAGE_NAME:latest . --load

echo "Tagging image for ACR..."
docker tag $IMAGE_NAME:latest $ACR_NAME/$IMAGE_NAME:latest

echo "Pushing image to ACR..."
docker push $ACR_NAME/$IMAGE_NAME:latest

echo "Restarting Azure App Service..."
az webapp restart --name $APP_SERVICE --resource-group $RESOURCE_GROUP

echo "Deployment complete!"
