# AI Voice Concierge - Deployment Guide

## Overview
This guide explains how to deploy the AI Voice Concierge application to Azure App Service using Docker containers.

## Prerequisites
- Azure CLI installed and authenticated
- Docker Desktop running
- Access to Azure Container Registry (ACR)
- Azure App Service with container support

## Environment Variables

### Required for Deployment
The following variables must be set in your `.env` file or shell environment:

```bash
APP_NAME=ai-voice-concierge-canadacentral
RESOURCE_GROUP=ai-concierge
ACR_NAME=aiconciergeregistry-eta2akbcfvfqfycd
IMAGE_NAME=ai-concierge:latest
```

**Important:** These variables must NOT have leading spaces in the `.env` file.

### Application Environment Variables
The application uses Azure Key Vault in production, but for local development, these can be set in `.env`:

```bash
# Azure OpenAI
AZURE_OPENAI_KEY=your_key_here
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4o-mini

# Twilio (if using)
TWILIO_ACCOUNT_SID=your_sid_here
TWILIO_AUTH_TOKEN=your_token_here
TWILIO_PHONE_NUMBER=+1234567890

# Phone Configuration
REAL_PHONE_NUMBER=+1234567890

# Database
USE_AZURE_SQL=true  # Set to false for local SQLite
SQLITE_DB_PATH=calls.db  # Only used if USE_AZURE_SQL=false
```

## Deployment Steps

### 1. Prepare Environment
```bash
# Load deployment variables from .env
export $(cat .env | grep -E '^(APP_NAME|RESOURCE_GROUP|ACR_NAME|IMAGE_NAME)=' | xargs)

# Or set them manually
export APP_NAME="ai-voice-concierge-canadacentral"
export RESOURCE_GROUP="ai-concierge"
export ACR_NAME="aiconciergeregistry-eta2akbcfvfqfycd"
export IMAGE_NAME="ai-concierge:latest"
```

### 2. Authenticate with Azure Container Registry
```bash
az acr login --name $ACR_NAME
```

### 3. Run Deployment Script
```bash
./deploy.sh
```

The deployment script will:
1. Build the Docker image
2. Tag it for ACR
3. Push to ACR
4. Update the App Service
5. Restart the App Service

## Troubleshooting

### Common Issues

#### 1. "APP_NAME: APP_NAME must be set"
**Cause:** Environment variables not loaded or `.env` file has formatting issues.
**Solution:** 
- Check that `.env` file has no leading spaces
- Verify variables are exported: `echo $APP_NAME`
- Use: `export $(cat .env | grep -E '^(APP_NAME|RESOURCE_GROUP|ACR_NAME|IMAGE_NAME)=' | xargs)`

#### 2. "401 Unauthorized" when pushing to ACR
**Cause:** Not authenticated with Azure Container Registry.
**Solution:** Run `az acr login --name $ACR_NAME`

#### 3. "Resource not found" errors
**Cause:** Incorrect resource names or not logged into correct Azure subscription.
**Solution:** 
- Verify resource names in Azure Portal
- Check current subscription: `az account show`
- Switch subscription if needed: `az account set --subscription <subscription-id>`

#### 4. Docker build failures
**Cause:** Missing dependencies or Docker issues.
**Solution:**
- Ensure Docker Desktop is running
- Check `requirements.txt` is up to date
- Clear Docker cache: `docker system prune`

### Debugging Commands

```bash
# Check Azure login status
az account show

# List available App Services
az webapp list --resource-group $RESOURCE_GROUP

# Check ACR authentication
az acr show --name $ACR_NAME

# View App Service logs
az webapp log tail --name $APP_NAME --resource-group $RESOURCE_GROUP

# Check deployment status
az webapp show --name $APP_NAME --resource-group $RESOURCE_GROUP --query "state"
```

## Manual Deployment (Alternative)

If the deploy script fails, you can deploy manually:

```bash
# 1. Build image
docker build -t $IMAGE_NAME .

# 2. Tag for ACR
docker tag $IMAGE_NAME $ACR_NAME.azurecr.io/$IMAGE_NAME

# 3. Push to ACR
docker push $ACR_NAME.azurecr.io/$IMAGE_NAME

# 4. Update App Service
az webapp config container set \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --container-image-name $ACR_NAME.azurecr.io/$IMAGE_NAME

# 5. Restart App Service
az webapp restart --name $APP_NAME --resource-group $RESOURCE_GROUP
```

## Post-Deployment Verification

### 1. Check Application Health
```bash
# Test the health endpoint
curl https://$APP_NAME.azurewebsites.net/
```

### 2. Check Logs
```bash
# View recent logs
./get_recent_logs.sh

# Or use Azure CLI
az webapp log tail --name $APP_NAME --resource-group $RESOURCE_GROUP
```

### 3. Test Database Connectivity
```bash
# Test database endpoint
curl https://$APP_NAME.azurewebsites.net/test-db
```

## Security Notes

- **Never commit `.env` files** to version control
- **Use Azure Key Vault** in production for all secrets
- **Rotate API keys** regularly
- **Monitor access logs** for suspicious activity

## Best Practices

1. **Always backup** before deployment: `cp .env .env.backup`
2. **Test locally** before deploying to production
3. **Use staging environments** for testing
4. **Monitor application metrics** after deployment
5. **Keep deployment scripts** in version control
6. **Document environment-specific** configurations

## Rollback Procedure

If deployment fails, you can rollback:

```bash
# Revert to previous image (if available)
az webapp config container set \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --container-image-name $ACR_NAME.azurecr.io/$IMAGE_NAME:previous

# Restart with previous version
az webapp restart --name $APP_NAME --resource-group $RESOURCE_GROUP
```

## Support

For deployment issues:
1. Check this guide first
2. Review Azure App Service logs
3. Verify all prerequisites are met
4. Test with manual deployment steps
5. Contact Azure support if needed

---

**Last Updated:** July 2024
**Version:** 1.0 