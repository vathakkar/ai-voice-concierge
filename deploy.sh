#!/bin/bash
# Deploy script for AI Voice Concierge - Canada Central
# Builds, pushes, and restarts the Canada Central Azure App Service
# All configuration is via environment variables for security and flexibility.

set -e

# --- Check Azure CLI login ---
if ! az account show > /dev/null 2>&1; then
  echo "You are not logged in to Azure CLI. Please run 'az login' and try again."
  exit 1
fi

# --- Configuration ---
# Set these environment variables before running the script, or export them in your shell/profile.
# Example:
#   export APP_NAME="ai-voice-concierge-canadacentral"
#   export RESOURCE_GROUP="ai-concierge"
#   export ACR_NAME="aiconciergeregistry-eta2akbcfvfqfycd"
#   export IMAGE_NAME="ai-concierge:latest"

: "${APP_NAME:?APP_NAME must be set}"
: "${RESOURCE_GROUP:?RESOURCE_GROUP must be set}"
: "${ACR_NAME:?ACR_NAME must be set}"
: "${IMAGE_NAME:?IMAGE_NAME must be set}"
: "${ACR_USERNAME:?ACR_USERNAME must be set}"
: "${ACR_PASSWORD:?ACR_PASSWORD must be set}"

ACR_IMAGE="$ACR_NAME.azurecr.io/$IMAGE_NAME"

# --- Docker login using ACR admin credentials ---
echo "Logging in to Azure Container Registry..."
echo $ACR_PASSWORD | docker login $ACR_NAME.azurecr.io -u $ACR_USERNAME --password-stdin

# --- Build Docker image for amd64 ---
echo "Building Docker image (linux/amd64)..."
docker build --platform linux/amd64 -t $IMAGE_NAME .

# --- Tag image for Azure Container Registry ---
echo "Tagging image for ACR..."
docker tag $IMAGE_NAME $ACR_IMAGE

# --- Push image to Azure Container Registry ---
echo "Pushing image to ACR..."
docker push $ACR_IMAGE

# --- Update App Service to use new image and restart ---
echo "Updating Azure App Service to use new image..."
az webapp config container set --name $APP_NAME --resource-group $RESOURCE_GROUP --docker-custom-image-name $ACR_IMAGE
az webapp restart --name $APP_NAME --resource-group $RESOURCE_GROUP

echo "Deployment complete!"
