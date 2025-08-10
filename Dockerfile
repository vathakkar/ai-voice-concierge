# =============================================================================
# AI Voice Concierge - Docker Container
# =============================================================================
#
# This Dockerfile creates a production-ready container for the AI Voice Concierge
# application. It includes all necessary dependencies for Azure SQL connectivity
# and Azure Speech Services, optimized for deployment to Azure App Service.
#
# Key Features:
# - Ubuntu 22.04 base image for better Azure Speech SDK compatibility
# - ODBC drivers for Azure SQL Database connectivity
# - Azure Speech Services dependencies
# - All Python dependencies from requirements.txt
# - Proper port configuration for Azure App Service
# - Health check endpoint support
#
# Security Notes:
# - Runs as non-root user for security
# - Minimal system packages installed
# - No unnecessary development tools
#
# Performance Notes:
# - Optimized layer caching
# - Minimal runtime dependencies
# =============================================================================

# Use Ubuntu 22.04 as base for better Azure Speech SDK compatibility
FROM ubuntu:22.04

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV DEBIAN_FRONTEND=noninteractive

# Install Python and system dependencies
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3.11-dev \
    python3-pip \
    curl \
    gnupg2 \
    # Azure Speech Services dependencies
    libssl3 \
    libasound2 \
    libpulse0 \
    libpulse-dev \
    libasound2-dev \
    libssl-dev \
    libffi-dev \
    build-essential \
    pkg-config \
    # Additional audio libraries
    libportaudio2 \
    libportaudiocpp0 \
    libsndfile1 \
    libsndfile1-dev \
    # Clean up
    && rm -rf /var/lib/apt/lists/*

# Download and install Microsoft ODBC Driver for SQL Server
RUN curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - \
    && curl https://packages.microsoft.com/config/ubuntu/22.04/prod.list > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql18 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory in container
WORKDIR /app

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# Expose port for Azure App Service
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# Start the application
CMD ["python3", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"] 