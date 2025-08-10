# AI Voice Concierge

## Overview
This project is a production-ready AI Voice Concierge system that answers phone calls, screens callers, and interacts using natural language. It is built with FastAPI, Twilio Voice, Azure OpenAI, and SQLite for persistent logging.

**Current Status**: Optimized for fast, natural conversations and smart decision making.

---

## Architecture
- **FastAPI**: Main backend server, handles Twilio webhooks and API endpoints.
- **Twilio Voice**: Receives calls, collects speech, and relays to FastAPI.
- **Azure OpenAI**: Provides the AI assistant logic for dynamic, context-aware responses.
- **Azure Speech Services**: High-quality, low-latency text-to-speech synthesis.
- **SQLite**: Stores all call and conversation logs for auditing and review (local only).
- **Azure Key Vault**: Stores secrets (API keys) securely.
- **Docker**: Containerized for easy deployment to Azure App Service.

---

## Safe Deployment Workflow (Test Before Prod)

To ensure only working builds reach production, use the `deploy_test.sh` script:

- **Local Build & Test:**
  - Builds the Docker image locally (ARM/native arch).
  - Runs the container locally with your `.env` file for all required environment variables.
  - Health-checks the running container (by default, curls the root endpoint).
  - If the local build or test fails, the script prints the error and aborts—nothing is pushed to production.
- **Production Deploy:**
  - If the local test passes, the script builds the image for `amd64`, pushes to Azure Container Registry, and updates your Azure App Service.
  - Uses the same environment variable pattern as production for consistency.

**Usage:**
```sh
export $(cat .env | grep -E '^(APP_NAME|RESOURCE_GROUP|ACR_NAME|IMAGE_NAME|ACR_USERNAME|ACR_PASSWORD)=' | xargs) && ./deploy_test.sh
```
Or simply:
```sh
./deploy_test.sh
```
if your `.env` file is present and contains the required variables.

**Benefits:**
- Prevents broken or misconfigured builds from reaching production.
- Ensures all required secrets and environment variables are present for both local and prod.
- Fast feedback loop for safe, reliable deployments.

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

#### SQLite Configuration
```bash
# SQLite Database Path
SQLITE_DB_PATH=calls.db
```

### Optional Environment Variables

#### Azure Speech Services (TTS Integration)
```bash
# Azure Speech Services Key (for high-quality TTS)
AZURE_SPEECH_KEY=your_azure_speech_key

# Azure Speech Services Region (for TTS service)
AZURE_SPEECH_REGION=westus2

# Text-to-Speech Voice (Azure neural voice)
TTS_VOICE=en-US-JennyNeural

# Enable/disable Azure TTS (fallback to Twilio if disabled)
USE_AZURE_TTS=true
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
   - **Greeting**: Azure Speech Services generates high-quality TTS for the greeting, then uses `<Gather input="speech">` to collect their reason for calling.
   - **AI Processing**: The caller's speech is sent to `/twilio/ai-response`, which uses Azure OpenAI to generate a natural, conversational response.
   - **TTS Synthesis**: Azure Speech Services converts AI responses to high-quality audio with ~100-200ms latency.
   - **Screening & Action**: The AI classifies the call and takes action:
     - **Transfer**: For urgent/legitimate calls, uses `{TRANSFER}` command to transfer to the real phone number
   - **End Call**: For non-urgent calls, ends call after AI response with suggestion to text if urgent
5. **Logging**: Every interaction is logged in the Azure SQL Database with timing information.
6. **Review**: Recent conversations can be viewed via the `/conversations` endpoint.

## Azure TTS Integration

### Benefits
- **Lower Latency**: ~100-200ms vs 500-800ms for Twilio Polly
- **Higher Quality**: Neural voices with better pronunciation and naturalness
- **SSML Support**: Advanced voice control for pacing, emphasis, and pronunciation
- **Audio Caching**: Common responses cached for faster playback
- **Graceful Fallback**: Falls back to Twilio TTS if Azure fails

### Configuration
- **AZURE_SPEECH_KEY**: Your Azure Speech Services API key
- **AZURE_SPEECH_REGION**: Your Azure Speech Services region (e.g., westus2)
- **TTS_VOICE**: Neural voice name (default: en-US-JennyNeural)
- **USE_AZURE_TTS**: Enable/disable Azure TTS (default: true)

### Testing
Run the test script to verify Azure TTS integration:
```bash
python test_azure_tts.py
```

### Fallback Behavior
If Azure TTS is unavailable or fails, the system automatically falls back to Twilio's built-in TTS to ensure call continuity.

## Conditional Forwarding & Call Screening Flow

- **Conditional Forwarding:** Your personal phone is set up with conditional call forwarding (e.g., "forward when busy" or "do not disturb") to your Twilio number.
- **Twilio Screening:** The Twilio number receives forwarded calls and passes them to the AI Voice Concierge for screening.
- **AI Screening:** The AI screens the call using Azure OpenAI, and either:
  - Forwards urgent/legitimate calls to your work phone (or real phone number), or
  - Ends the call with a helpful message for non-urgent callers.
- **Benefit:** When your phone is in work or sleep mode, only urgent/screened calls are forwarded to your work phone, so you only answer calls that matter.

This setup ensures you are not disturbed by non-urgent calls and only answer those that have been screened by the AI system.

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

## Performance

### Latest Performance Test Results (August 2025)
- **Tested Model:** GPT-4o-mini, Azure Speech Services
- **Scenarios:** All 5 scenarios completed successfully (no rate limit errors)
- **End-to-end SLO (P95 < 3000ms):** PASS (P95 = 2248ms)
- **Endpoint latency SLO (P95 < 100ms):** FAIL (P95 = 624ms for /twilio/voice, 1799ms for /twilio/process-ai)
- **TTS/AI Processing Time:** No data captured (check logging/extraction)
- **Memory Usage:** Avg 25.6MB, Peak 30.6MB
- **Test Method:** 65-second delay between scenarios to avoid Azure OpenAI rate limits

### Competition Analysis & Industry Benchmarks

#### Market Performance Standards
- **Enterprise Voice AI (Google Dialogflow, Amazon Lex):**
  - End-to-end response: 2-4 seconds (P95)
  - TTS latency: 200-500ms
  - AI processing: 1-3 seconds
  - **Our Performance:** Competitive with enterprise solutions

- **Consumer Voice Assistants (Siri, Alexa, Google Assistant):**
  - End-to-end response: 1-3 seconds (P95)
  - TTS latency: 100-300ms
  - AI processing: 500ms-2 seconds
  - **Our Performance:** Comparable to consumer-grade systems

- **Call Center AI (Genesys, Avaya):**
  - End-to-end response: 3-6 seconds (P95)
  - TTS latency: 300-800ms
  - AI processing: 2-4 seconds
  - **Our Performance:** Significantly faster than traditional call center solutions

#### Competitive Advantages
1. **Speed:** Our P95 of 2248ms beats most enterprise call screening solutions
2. **Cost:** Azure OpenAI GPT-4o-mini provides enterprise-grade AI at consumer pricing
3. **Quality:** Azure Speech Services neural voices match premium TTS providers
4. **Reliability:** 100% success rate in recent tests with proper rate limit management

#### Areas for Improvement
1. **Endpoint Latency:** Current P95 of 1799ms for AI processing exceeds 100ms target
2. **Rate Limiting:** Requires 65-second delays between calls to avoid Azure OpenAI limits
3. **TTS Metrics:** Need better instrumentation for TTS generation timing

#### Industry Positioning
- **Performance Tier:** Mid-enterprise (competitive with $50K+ annual solutions)
- **Cost Tier:** Consumer/SMB (fraction of enterprise pricing)
- **Quality Tier:** Enterprise-grade (Azure OpenAI + Azure Speech Services)
- **Scalability:** Production-ready with Azure App Service infrastructure

---

## Call Handling Logic
- **Transfer Decision**: When AI response contains `{TRANSFER}`, call is transferred to `REAL_PHONE_NUMBER`
- **Fallback Logic**: If transfer fails (busy/no answer), caller is prompted to text if urgent
- **Default**: Call ends after AI response for non-urgent scenarios
- **No Speech**: Call ends after retry attempts if no speech is detected

---

## Logging
Every call and conversation turn is logged in the SQLite database (local only). 

---

## Database Schema
- **calls**: One row per call (caller_id, start_time, end_time, final_decision, summary, outcome)
- **conversation**: One row per turn (call_id, turn_index, speaker, text, timestamp)
- **exception_phone_numbers**: Family/friends/favorite contacts that bypass AI screening
- **call_summaries**: One row per call, asynchronously logged after call ends. Includes call_id, caller_id, start_time, end_time, final_decision, summary, full_conversation (JSON), created_at.
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
- Visit `https://your-app.azurewebsites.net/conversations`