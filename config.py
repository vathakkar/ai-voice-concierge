import os
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
import logging

# Load environment variables from .env file
load_dotenv()

def get_secret_from_keyvault(secret_name, fallback_env_var=None):
    """
    Try to get a secret from Azure Key Vault, fallback to environment variable
    """
    try:
        # Only try Key Vault if we're in Azure (check for WEBSITE_SITE_NAME)
        if os.getenv('WEBSITE_SITE_NAME'):
            credential = DefaultAzureCredential()
            vault_url = f"https://ai-concierge-vault.vault.azure.net/"
            client = SecretClient(vault_url=vault_url, credential=credential)
            secret = client.get_secret(secret_name)
            return secret.value
        else:
            # Not in Azure, use environment variable
            return os.getenv(fallback_env_var or secret_name)
    except Exception as e:
        logging.warning(f"Failed to get secret {secret_name} from Key Vault: {e}")
        # Fallback to environment variable
        return os.getenv(fallback_env_var or secret_name)

# Azure Communication Services
ACS_CONNECTION_STRING = get_secret_from_keyvault('ACS-CONNECTION-STRING', 'ACS_CONNECTION_STRING')
ACS_PHONE_NUMBER = get_secret_from_keyvault('ACS-PHONE-NUMBER', 'ACS_PHONE_NUMBER')
REAL_PHONE_NUMBER = get_secret_from_keyvault('REAL-PHONE-NUMBER', 'REAL_PHONE_NUMBER')

# Azure Speech Services
AZURE_SPEECH_KEY = get_secret_from_keyvault('AZURE-SPEECH-KEY', 'AZURE_SPEECH_KEY')
AZURE_SPEECH_REGION = get_secret_from_keyvault('AZURE-SPEECH-REGION', 'AZURE_SPEECH_REGION')

# Azure OpenAI
AZURE_OPENAI_KEY = get_secret_from_keyvault('AZURE-OPENAI-KEY', 'AZURE_OPENAI_KEY')
AZURE_OPENAI_ENDPOINT = get_secret_from_keyvault('AZURE-OPENAI-ENDPOINT', 'AZURE_OPENAI_ENDPOINT')
AZURE_OPENAI_DEPLOYMENT = get_secret_from_keyvault('AZURE-OPENAI-DEPLOYMENT', 'AZURE_OPENAI_DEPLOYMENT')

# Azure SQL Database
AZURE_SQL_CONNECTION_STRING = get_secret_from_keyvault('AZURE-SQL-CONNECTION-STRING', 'AZURE_SQL_CONNECTION_STRING')

# SQLite
SQLITE_DB_PATH = os.getenv('SQLITE_DB_PATH', 'calls.db')  # Path to SQLite database file

# Other config
TTS_VOICE = os.getenv('TTS_VOICE', 'en-US-JennyNeural')  # Default TTS voice 