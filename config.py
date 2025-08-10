"""
Configuration Management for AI Voice Concierge
===============================================

This module handles all configuration and secrets management for the application.
It provides a secure way to load API keys and configuration values from either
Azure Key Vault (in production) or environment variables (in development).

Security Features:
- Azure Key Vault integration for production secrets
- Environment variable fallback for development
- No hardcoded secrets in the codebase
- Automatic detection of Azure environment

Important: Never commit API keys or secrets to version control.
All sensitive information should be stored in Azure Key Vault or environment variables.
"""

import os
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
import logging

# Dump all environment variables at startup for debugging
logging.basicConfig(level=logging.INFO)
logging.info("==== ENVIRONMENT VARIABLES AT STARTUP ====")
for k, v in os.environ.items():
    if 'PASSWORD' in k or 'KEY' in k or 'SECRET' in k:
        logging.info(f"{k}=***MASKED***")
    else:
        logging.info(f"{k}={v}")
logging.info("==== END ENVIRONMENT VARIABLES DUMP ====")

# Load environment variables from .env file (for local development)
# Note: .env file should be in .gitignore and never committed
load_dotenv()

def get_secret_from_keyvault(secret_name, fallback_env_var=None):
    """
    Securely retrieve secrets from Azure Key Vault or environment variables
    
    This function implements a secure secrets management strategy:
    1. In Azure App Service: Uses Azure Key Vault with managed identity
    2. In local development: Falls back to environment variables
    3. Provides logging for debugging secret retrieval issues
    
    Args:
        secret_name: Name of the secret in Azure Key Vault
        fallback_env_var: Environment variable name to use as fallback
        
    Returns:
        str: The secret value or None if not found
        
    Security Note: This function never logs the actual secret values,
    only the success/failure of retrieval attempts.
    """
    try:
        # Check if we're running in Azure App Service
        if os.getenv('WEBSITE_SITE_NAME'):
            # Production: Use Azure Key Vault with managed identity
            logging.info(f"Running in Azure App Service, attempting to retrieve '{secret_name}' from Key Vault")
            credential = DefaultAzureCredential()
            vault_url = f"https://ai-concierge-vault.vault.azure.net/"
            client = SecretClient(vault_url=vault_url, credential=credential)
            secret = client.get_secret(secret_name)
            logging.info(f"Successfully retrieved secret '{secret_name}' from Azure Key Vault")
            logging.info(f"Secret value length: {len(secret.value) if secret.value else 0}")
            return secret.value
        else:
            # Development: Use environment variables
            env_var = fallback_env_var or secret_name
            value = os.getenv(env_var)
            if value:
                logging.info(f"Retrieved '{secret_name}' from environment variable '{env_var}'")
                logging.info(f"Environment variable value length: {len(value)}")
            else:
                logging.warning(f"Environment variable '{env_var}' not found for secret '{secret_name}'")
            return value
    except Exception as e:
        # Log the error but don't expose sensitive information
        logging.warning(f"Failed to get secret '{secret_name}' from Key Vault: {str(e)}")
        # Fallback to environment variable
        env_var = fallback_env_var or secret_name
        value = os.getenv(env_var)
        if value:
            logging.info(f"Using fallback environment variable '{env_var}' for '{secret_name}'")
            logging.info(f"Fallback value length: {len(value)}")
        else:
            logging.error(f"Both Key Vault and fallback environment variable '{env_var}' failed for '{secret_name}'")
        return value

# =============================================================================
# AZURE COMMUNICATION SERVICES CONFIGURATION
# =============================================================================
# Note: These are legacy configurations from the previous ACS implementation
# They are kept for reference but not actively used in the current Twilio-based system

ACS_CONNECTION_STRING = get_secret_from_keyvault('ACS-CONNECTION-STRING', 'ACS_CONNECTION_STRING')
ACS_PHONE_NUMBER = get_secret_from_keyvault('ACS-PHONE-NUMBER', 'ACS_PHONE_NUMBER')

# =============================================================================
# PHONE NUMBER CONFIGURATION
# =============================================================================
# The phone number where urgent calls will be transferred

REAL_PHONE_NUMBER = get_secret_from_keyvault('REAL-PHONE-NUMBER', 'REAL_PHONE_NUMBER')

# =============================================================================
# AZURE SPEECH SERVICES CONFIGURATION
# =============================================================================
# Note: These are currently unused but kept for potential future features
# The current implementation uses Twilio's built-in speech recognition

AZURE_SPEECH_KEY = get_secret_from_keyvault('AZURE-SPEECH-KEY', 'AZURE_SPEECH_KEY')
AZURE_SPEECH_REGION = get_secret_from_keyvault('AZURE-SPEECH-REGION', 'AZURE_SPEECH_REGION')

# =============================================================================
# AZURE OPENAI CONFIGURATION
# =============================================================================
# Core AI service configuration for call screening and response generation

# Primary OpenAI service (East US - FASTER)
AZURE_OPENAI_KEY = get_secret_from_keyvault('AZURE-OPENAI-KEY-EASTUS', 'AZURE_OPENAI_KEY_EASTUS')
AZURE_OPENAI_ENDPOINT = get_secret_from_keyvault('AZURE-OPENAI-ENDPOINT-EASTUS', 'AZURE_OPENAI_ENDPOINT_EASTUS')
AZURE_OPENAI_DEPLOYMENT = get_secret_from_keyvault('AZURE-OPENAI-DEPLOYMENT-EASTUS', 'AZURE_OPENAI_DEPLOYMENT_EASTUS')

# Fallback to original service if East US not available
if not AZURE_OPENAI_KEY or not AZURE_OPENAI_ENDPOINT or not AZURE_OPENAI_DEPLOYMENT:
    AZURE_OPENAI_KEY = get_secret_from_keyvault('AZURE-OPENAI-KEY', 'AZURE_OPENAI_KEY')
    AZURE_OPENAI_ENDPOINT = get_secret_from_keyvault('AZURE-OPENAI-ENDPOINT', 'AZURE_OPENAI_ENDPOINT')
    AZURE_OPENAI_DEPLOYMENT = get_secret_from_keyvault('AZURE-OPENAI-DEPLOYMENT', 'AZURE_OPENAI_DEPLOYMENT')

# =============================================================================
# DATABASE CONFIGURATION
# =============================================================================
# Database connection configuration for call logging

AZURE_SQL_CONNECTION_STRING = get_secret_from_keyvault('AZURE-SQL-CONNECTION-STRING', 'AZURE_SQL_CONNECTION_STRING')

# =============================================================================
# LOCAL DEVELOPMENT CONFIGURATION
# =============================================================================
# Configuration for local development and testing

# Database mode configuration
# Set to 'true' to use Azure SQL in production, 'false' for SQLite in development
USE_AZURE_SQL = os.getenv('USE_AZURE_SQL', 'false').lower() == 'true'

# SQLite database path for local development
# Note: In production, USE_AZURE_SQL should be set to 'true'
SQLITE_DB_PATH = os.getenv('SQLITE_DB_PATH', 'calls.db')

# =============================================================================
# TEXT-TO-SPEECH CONFIGURATION
# =============================================================================
# TTS voice configuration for Azure Speech Services

TTS_VOICE = os.getenv('TTS_VOICE', 'en-US-JennyNeural')

# TTS service configuration
USE_AZURE_TTS = os.getenv('USE_AZURE_TTS', 'true').lower() == 'true'

# Pre-generation configuration
# Set to 'false' to skip TTS pre-generation (useful for local testing)
ENABLE_TTS_PREGEN = os.getenv('ENABLE_TTS_PREGEN', 'true').lower() == 'true'

# =============================================================================
# VOICE MESSAGES CONFIGURATION
# =============================================================================
# Common voice messages that are frequently used and can be pre-generated

# Initial greeting message for incoming calls
GREETING_MESSAGE = os.getenv('GREETING_MESSAGE', 
    "Hi, I'm Vansh's virtual assistant. He's busy right now, but I can take the reason for your call and either transfer you or notify him to get back to you. What's the reason for your call today?")

# "One moment" message for processing delays
ONE_MOMENT_MESSAGE = os.getenv('ONE_MOMENT_MESSAGE', "One moment.")

# Retry message when no speech is detected
RETRY_MESSAGE = os.getenv('RETRY_MESSAGE', "I didn't hear anything. Can you please repeat how I can help?")

# Final retry message before ending call
FINAL_RETRY_MESSAGE = os.getenv('FINAL_RETRY_MESSAGE', "Sorry, I still didn't hear anything. Goodbye!")

# Transfer message for exception contacts
TRANSFER_MESSAGE = os.getenv('TRANSFER_MESSAGE', "Transferring you now.")

# Fallback message for transfer failures
TRANSFER_FALLBACK_MESSAGE = os.getenv('TRANSFER_FALLBACK_MESSAGE', 
    "Unfortunately Vansh is on another call. Please text him and he will get back to you as soon as possible.")

# Error messages
ERROR_MESSAGE_ERR01 = os.getenv('ERROR_MESSAGE_ERR01', 
    "I am experiencing an outage, please call back later. Goodbye! Error code: ERR01")
ERROR_MESSAGE_ERR02 = os.getenv('ERROR_MESSAGE_ERR02', 
    "Sorry, there was an error. Goodbye! Error code: ERR02")
ERROR_MESSAGE_ERR03 = os.getenv('ERROR_MESSAGE_ERR03', 
    "Unfortunately Vansh is unavailable. Please text him and he will get back to you as soon as possible. Error code: ERR03") 
# =============================================================================
# TWILIO CONFIGURATION
# =============================================================================
# Twilio secrets and phone number for webhook validation and call handling

TWILIO_ACCOUNT_SID = get_secret_from_keyvault('TWILIO-ACCOUNT-SID', 'TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = get_secret_from_keyvault('TWILIO-AUTH-TOKEN', 'TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = get_secret_from_keyvault('TWILIO-PHONE-NUMBER', 'TWILIO_PHONE_NUMBER') 