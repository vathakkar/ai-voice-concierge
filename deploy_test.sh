#!/bin/bash
# Test-then-Deploy script for AI Voice Concierge - Canada Central
# Builds and tests locally (ARM), then deploys to prod (amd64) only if local build/test passes.

set -e

# --- Optionally source .env for local development ---
if [ -f .env ]; then
  export $(cat .env | grep -E '^(APP_NAME|RESOURCE_GROUP|ACR_NAME|IMAGE_NAME|ACR_USERNAME|ACR_PASSWORD)=' | xargs)
fi

# --- Check Azure CLI login ---
if ! az account show > /dev/null 2>&1; then
  echo "You are not logged in to Azure CLI. Please run 'az login' and try again."
  exit 1
fi

# --- Configuration ---
: "${APP_NAME:?APP_NAME must be set}"
: "${RESOURCE_GROUP:?RESOURCE_GROUP must be set}"
: "${ACR_NAME:?ACR_NAME must be set}"
: "${IMAGE_NAME:?IMAGE_NAME must be set}"
: "${ACR_USERNAME:?ACR_USERNAME must be set}"
: "${ACR_PASSWORD:?ACR_PASSWORD must be set}"

ACR_IMAGE="$ACR_NAME.azurecr.io/$IMAGE_NAME"

# --- Local build (ARM) ---
echo "Building Docker image locally (native arch, ARM)..."
if ! docker build -t $IMAGE_NAME .; then
  echo "Local Docker build failed. Aborting deployment."
  exit 1
fi

echo "Running local container for health check..."
CONTAINER_ID=$(docker run --env-file .env -d -p 8000:8000 $IMAGE_NAME)
sleep 8

# Health check: try to curl the root endpoint
if curl -sSf http://localhost:8000/ > /dev/null; then
  echo "Local container started successfully. Stopping and removing test container."
  docker stop $CONTAINER_ID > /dev/null
  docker rm $CONTAINER_ID > /dev/null
else
  echo "Local container health check failed. Stopping and removing test container."
  docker logs $CONTAINER_ID
  docker stop $CONTAINER_ID > /dev/null
  docker rm $CONTAINER_ID > /dev/null
  exit 1
fi

echo "Local build and test passed. Proceeding to production deployment..."

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

# --- Post-deployment health check ---
APP_URL="https://${APP_NAME}.azurewebsites.net/"
echo "Waiting for app to start..."
sleep 20

HEALTH_RESPONSE=$(curl -s -m 10 "$APP_URL")
if echo "$HEALTH_RESPONSE" | grep -qi 'healthy'; then
  echo "Production health check passed! App is running: $APP_URL"
else
  echo "Production health check failed!"
  echo "App response: $HEALTH_RESPONSE"
  echo "Fetching last 100 lines of logs for debugging using get_recent_logs.sh..."
  ./get_recent_logs.sh
  LATEST_LOG=$(ls -t logs/LogFiles/*docker.log 2>/dev/null | head -n1)
  if [ -f "$LATEST_LOG" ]; then
    echo "--- Last 100 lines of $LATEST_LOG ---"
    tail -n 100 "$LATEST_LOG"
  else
    echo "No docker log file found."
  fi
  exit 2
fi 