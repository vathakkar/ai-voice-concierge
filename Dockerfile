# =============================================================================
# AI Voice Concierge - Docker Container
# =============================================================================
#
# This Dockerfile creates a production-ready container for the AI Voice Concierge
# application. It includes all necessary dependencies for Azure SQL connectivity
# and optimized for deployment to Azure App Service.
#
# Key Features:
# - Python 3.11 slim base image for security and size optimization
# - ODBC drivers for Azure SQL Database connectivity
# - All Python dependencies from requirements.txt
# - Proper port configuration for Azure App Service
# - Health check endpoint support
#
# Security Notes:
# - Uses slim base image to minimize attack surface
# - Runs as non-root user (handled by Azure App Service)
# - No secrets or sensitive data in the image
# =============================================================================

# Use Python 3.11 slim image as base
# Slim images are smaller and more secure than full Python images
FROM python:3.11-slim

# Set working directory in container
WORKDIR /app

# Copy requirements file first for better Docker layer caching
# This allows Docker to cache the pip install step if requirements.txt hasn't changed
COPY requirements.txt .

# Remove ODBC/pyodbc installation steps; only install build tools and requirements
RUN apt-get update && apt-get install -y gcc g++ gnupg2
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code to container
# This includes all Python files, static assets, and configuration
COPY . .

# Expose port 8000 for FastAPI application
# Azure App Service will map this to the appropriate external port
EXPOSE 8000

# Start the FastAPI application using uvicorn
# Uses environment variable PORT for Azure App Service compatibility
# --host 0.0.0.0 allows external connections
# --port ${PORT:-8000} uses PORT env var or defaults to 8000
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"] 