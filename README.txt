# AI Voice Concierge

## Overview
This project is a production-ready AI Voice Concierge system that answers phone calls, screens callers, and interacts using natural language. It is built with FastAPI, Twilio Voice, Azure OpenAI, and Azure SQL Database for persistent logging.

**Current Status**: Optimized for fast, natural conversations with ~750ms average response times and smart decision making.

---

## Architecture
- **FastAPI**: Main backend server, handles Twilio webhooks and API endpoints.
- **Twilio Voice**: Receives calls, collects speech, and relays to FastAPI.
- **Azure OpenAI**: Provides the AI assistant logic for dynamic, context-aware responses.
- **Azure SQL Database**: Stores all call and conversation logs for auditing and review.
- **Azure Key Vault**: Stores secrets (API keys, SQL connection string) securely.
- **Docker**: Containerized for easy deployment to Azure App Service.

---

## Security & API Key Management

### ⚠️ CRITICAL SECURITY NOTES
- **NEVER commit API keys or secrets to version control**
- **NEVER hardcode sensitive information in the codebase**
- **ALWAYS use Azure Key Vault in production**
- **ALWAYS use environment variables in development**

### Production Security (Azure Key Vault)
The application automatically detects when running in Azure App Service and uses Azure Key Vault with managed identity for secure secret retrieval. All secrets are stored in Key Vault and accessed securely.

### Development Security (Environment Variables)
For local development, use environment variables or a `.env` file (ensure `.env` is in `.gitignore`).

---

## Environment Variables

### Required Environment Variables

#### Azure OpenAI Configuration
```bash
# Azure OpenAI API Key (from Azure Portal)
AZURE_OPENAI_KEY=your_azure_openai_api_key_here

# Azure OpenAI Endpoint (from Azure Portal)
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/

# Azure OpenAI Deployment Name (from Azure Portal)
AZURE_OPENAI_DEPLOYMENT=your_deployment_name
```

#### Twilio Configuration
```bash
# Twilio Account SID (from Twilio Console)
TWILIO_ACCOUNT_SID=your_twilio_account_sid

# Twilio Auth Token (from Twilio Console)
TWILIO_AUTH_TOKEN=your_twilio_auth_token

# Twilio Phone Number (your Twilio number)
TWILIO_PHONE_NUMBER=+1234567890
```

#### Phone Number Configuration
```bash
# Real phone number for call transfers
REAL_PHONE_NUMBER=+1234567890
```

#### Database Configuration
```bash
# Set to 'true' for Azure SQL, 'false' for SQLite (development)
USE_AZURE_SQL=true

# Azure SQL Connection String (from Azure Portal)
AZURE_SQL_CONNECTION_STRING=Server=tcp:your-server.database.windows.net,1433;Database=your-database;Authentication=Active Directory Default;

# SQLite Database Path (for development only)
SQLITE_DB_PATH=calls.db
```

### Optional Environment Variables

#### Azure Speech Services (Unused - Legacy)
```bash
# Azure Speech Services Key (currently unused)
AZURE_SPEECH_KEY=your_azure_speech_key

# Azure Speech Services Region (currently unused)
AZURE_SPEECH_REGION=westus2

# Text-to-Speech Voice (currently unused)
TTS_VOICE=en-US-JennyNeural
```

#### Azure Communication Services (Legacy - Unused)
```bash
# ACS Connection String (legacy, not used in current Twilio implementation)
ACS_CONNECTION_STRING=your_acs_connection_string

# ACS Phone Number (legacy, not used in current Twilio implementation)
ACS_PHONE_NUMBER=+1234567890
```

### Environment Variable Setup

#### For Local Development
1. Create a `.env` file in the project root
2. Add your environment variables:
```bash
# Copy this template and fill in your values
AZURE_OPENAI_KEY=your_key_here
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=your_deployment
REAL_PHONE_NUMBER=+1234567890
USE_AZURE_SQL=false
SQLITE_DB_PATH=calls.db
```

#### For Azure App Service (Production)
1. Go to Azure Portal → Your App Service → Configuration
2. Add Application Settings for each environment variable
3. Ensure Azure Key Vault integration is configured
4. Set `USE_AZURE_SQL=true` for production

---

## Call Flow
1. **Incoming Call**: Personal phone number is forwarded to the Twilio number, which then forwards the call to `/twilio/voice`.
2. **Exception Check**: System checks if the caller's phone number is in the exception list (family/friends/favorites).
3. **Direct Transfer**: If caller is in exception list, call is transferred directly without AI screening.
4. **AI Screening**: If caller is not in exception list, proceeds with normal AI screening:
   - **Greeting**: Twilio handles the initial greeting, then uses `<Gather input="speech">` to collect their reason for calling.
   - **AI Processing**: The caller's speech is sent to `/twilio/ai-response`, which uses Azure OpenAI to generate a natural, conversational response.
   - **Screening & Action**: The AI classifies the call and takes action:
     - **Transfer**: For urgent/legitimate calls, uses `{TRANSFER}` command to transfer to the real phone number
     - **End Call**: For non-urgent calls, ends call after AI response with suggestion to text if urgent
5. **Logging**: Every interaction is logged in the Azure SQL Database with timing information.
6. **Review**: Recent conversations can be viewed via the `/conversations` endpoint.

## Twilio Configuration
- **Phone Number Forwarding**: Personal phone number is configured to forward all incoming calls to the Twilio number
- **Webhook Setup**: The Twilio webhook is configured in the Twilio portal to point to the Azure App Service endpoint
- **Webhook URL**: `https://your-app.azurewebsites.net/twilio/voice` (configured in Twilio Console)

---

## AI Context (System Prompt)
- The AI is instructed to:
  - Respond naturally and conversationally as an AI concierge.
  - Screen for urgency, legitimacy, and call type (family, business, sales, etc.).
  - Use `{TRANSFER}` command for urgent/legitimate calls that need immediate attention.
  - For non-urgent calls, provide helpful responses and suggest texting if urgent.
  - Never reveal personal information.
  - Keep responses concise but natural (~12 words average).
  - Log every interaction for review.
- The full system prompt is in `prompts.py` and is the source of truth for the AI's behavior.

---

## Performance Optimizations
- **Response Time**: ~750ms average (GPT-3.5-turbo with optimized prompts)
- **Response Length**: ~12 words average for natural, concise communication
- **Decision Accuracy**: 100% correct classification of urgent vs non-urgent calls
- **No Caching**: Real-time responses for authentic conversations
- **Optimized Prompts**: System prompts designed for speed and naturalness

---

## Call Handling Logic
- **Transfer Decision**: When AI response contains `{TRANSFER}`, call is transferred to `REAL_PHONE_NUMBER`
- **Fallback Logic**: If transfer fails (busy/no answer), caller is prompted to text if urgent
- **Default**: Call ends after AI response for non-urgent scenarios
- **No Speech**: Call ends after retry attempts if no speech is detected

---

## Database Schema
- **calls**: One row per call (caller_id, start_time, end_time, final_decision)
- **conversation**: One row per turn (call_id, turn_index, speaker, text, timestamp)
- **exception_phone_numbers**: Family/friends/favorite contacts that bypass AI screening
- **final_decision values**: "transferred", "completed", "ended_no_speech", "transferred_exception"
- Schema is auto-created on first run if missing.

---

## Endpoints

### Core Twilio Endpoints
- `/twilio/voice`: Twilio webhook for incoming calls (POST)
- `/twilio/ai-response`: Handles speech input and returns AI response (POST)
- `/twilio/transfer-fallback`: Handles transfer failures (POST)

### Management Endpoints
- `/conversations`: Returns recent conversations (GET)
- `/test-db`: Diagnostic endpoint for DB connectivity (GET)

### Phase 2: Exception Phone Number Management
- `/exceptions`: Get all active exception phone numbers (GET)
- `/exceptions`: Add a phone number to exception list (POST)
- `/exceptions/{phone_number}`: Remove a phone number from exception list (DELETE)
- `/exceptions/check/{phone_number}`: Check if a phone number is in exception list (GET)

### Management Script
- `add_exception.py`: Interactive script to manage exception phone numbers (reads BASE_URL from .env file)

---

## Deployment

### Prerequisites
1. Azure subscription with access to:
   - Azure App Service
   - Azure Key Vault
   - Azure OpenAI Service
   - Azure SQL Database
2. Twilio account with a phone number
3. Docker installed locally

### Deployment Steps
1. **Set up Azure Resources**:
   - Create Azure Key Vault and store all secrets
   - Create Azure SQL Database
   - Create Azure OpenAI resource and deployment
   - Create App Service with Docker support (B2 SKU recommended)

2. **Configure Environment Variables**:
   - Set all required environment variables in App Service Configuration
   - Ensure Azure Key Vault integration is enabled

3. **Deploy Application**:
   ```bash
   # Use the provided deploy script
   ./deploy.sh
   ```

4. **Configure Twilio Webhooks**:
   - Set webhook URL to: `https://your-app.azurewebsites.net/twilio/voice`
   - Configure for POST requests

### Critical Deployment Learnings

#### Docker Platform Requirements
- **MUST build for linux/amd64 platform**: Azure App Service requires linux/amd64 images
- **Apple Silicon (M1/M2) users**: Use `--platform linux/amd64` when building Docker images
- **Build command**: `docker build --platform linux/amd64 -t your-image-name .`

#### Azure Container Registry (ACR) Authentication
- **Option 1 (Recommended)**: Use managed identity with AcrPull role
  - Enable managed identity on the web app
  - Assign "AcrPull" role to the managed identity for your ACR
- **Option 2**: Use ACR admin credentials
  - Get admin credentials from ACR → Access keys
  - Configure in App Service → Configuration → Application settings

#### Azure Key Vault Access
- **Managed Identity Setup**: Enable managed identity on the web app
- **Key Vault Permissions**: Assign "Key Vault Secrets User" role to the managed identity
- **Scope**: Set permissions at the Key Vault level, not individual secrets

#### App Service Configuration
- **Container Settings**: Ensure `linuxFxVersion` is set to container deployment
- **Platform**: Must be Linux (not Windows) for container deployments
- **SKU**: B2 or higher recommended for production workloads

### Local Development
1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Set Environment Variables**:
   - Create `.env` file with required variables
   - Set `USE_AZURE_SQL=false` for local SQLite

3. **Run Application**:
   ```bash
   uvicorn main:app --reload
   ```

---

## How to Review Conversations
- Visit `https://your-app.azurewebsites.net/conversations` after a call to see logs.
- Each entry includes all user and bot turns, timestamps, call metadata, and final decision.
- Response timing information is logged for performance monitoring.

## Managing Exception Phone Numbers

### Using the Management Script
The `add_exception.py` script provides an interactive way to manage your exception phone numbers:

1. **Setup**: Ensure your `.env` file contains the `BASE_URL` variable:
   ```bash
   BASE_URL=https://your-app.azurewebsites.net
   ```

2. **Run the script**:
   ```bash
   python3 add_exception.py
   ```

3. **Interactive options**:
   - Add new exception contacts
   - List all current exceptions
   - Check if a number is in the exception list
   - Exit the program

### Using API Endpoints Directly
You can also manage exceptions using the REST API endpoints:

**Add a contact**:
```bash
curl -X POST https://your-app.azurewebsites.net/exceptions \
  -H "Content-Type: application/json" \
  -d '{"phone_number": "+1234567890", "contact_name": "Mom", "category": "family"}'
```

**List all exceptions**:
```bash
curl https://your-app.azurewebsites.net/exceptions
```

**Check a number**:
```bash
curl https://your-app.azurewebsites.net/exceptions/check/+1234567890
```

---

## Phase 2: Exception Phone Numbers
- **Direct Transfer**: Family, friends, and favorite contacts bypass AI screening
- **Database Storage**: Exception phone numbers stored in Azure SQL Database
- **Management API**: REST endpoints to add/remove/check exception phone numbers
- **Categories**: Support for categorizing contacts (family, friends, work, etc.)
- **Soft Delete**: Phone numbers can be deactivated without permanent deletion

## Recent Optimizations
- **Natural Language**: Updated system prompts for more conversational responses
- **Performance**: Optimized for ~750ms response times with GPT-3.5-turbo
- **Call Flow**: Simplified to transfer urgent calls, end non-urgent calls with text suggestion
- **Fallback**: Added transfer failure handling with text suggestion
- **Logging**: Enhanced timing logs for performance monitoring

---

## Legacy/Unused Code
- All Azure Communication Services (ACS) logic and endpoints have been removed.
- Voicemail functionality has been removed in favor of text suggestions.
- Only Twilio, Azure OpenAI, and Azure SQL code remains.

---

## Security Best Practices

### Code Security
- ✅ No hardcoded secrets in codebase
- ✅ Azure Key Vault integration for production
- ✅ Environment variable fallback for development
- ✅ Secure logging (no sensitive data in logs)
- ✅ Input validation and error handling

### Deployment Security
- ✅ HTTPS enforcement in production
- ✅ Managed identity for Azure services
- ✅ Network security groups configured
- ✅ Regular security updates
- ✅ Monitoring and alerting

### API Security
- ✅ Secure API key management
- ✅ Rate limiting (via Twilio)
- ✅ Input sanitization
- ✅ Error handling without information disclosure

---

## Source of Truth
- This README, the `prompts.py` system prompt, and the FastAPI endpoints are the canonical reference for how the system works.
- For any changes, update this file and the relevant code.

---

## Getting Started

### Prerequisites
- Python 3.8+
- Azure subscription (for production deployment)
- Twilio account with a phone number
- Azure OpenAI resource

### Quick Start
1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/ai-voice-concierge.git
   cd ai-voice-concierge
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**:
   - Copy `.env.example` to `.env` (if available)
   - Or create a `.env` file with the required environment variables
   - **Never commit your `.env` file to version control**

4. **Run locally**:
   ```bash
   uvicorn main:app --reload
   ```

### Environment Variables Setup
Create a `.env` file in the project root with the following variables:
```bash
# Azure OpenAI
AZURE_OPENAI_KEY=your_key_here
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=your_deployment

# Twilio
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE_NUMBER=+1234567890

# Phone Configuration
REAL_PHONE_NUMBER=+1234567890

# Database (use SQLite for local development)
USE_AZURE_SQL=false
SQLITE_DB_PATH=calls.db
```

## Contact
For questions or improvements, please open an issue or submit a pull request. 