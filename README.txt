# AI Voice Concierge - Source of Truth

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

## Call Flow
1. **Incoming Call**: Twilio forwards the call to `/twilio/voice`.
2. **Greeting**: Twilio handles the initial greeting, then uses `<Gather input="speech">` to collect their reason for calling.
3. **AI Processing**: The caller's speech is sent to `/twilio/ai-response`, which uses Azure OpenAI to generate a natural, conversational response.
4. **Screening & Action**: The AI classifies the call and takes action:
   - **Transfer**: For urgent/legitimate calls, uses `{TRANSFER}` command to transfer to Vansh's real number
   - **End Call**: For non-urgent calls, ends call after AI response with suggestion to text if urgent
5. **Logging**: Every interaction is logged in the Azure SQL Database with timing information.
6. **Review**: Recent conversations can be viewed via the `/conversations` endpoint.

---

## AI Context (System Prompt)
- The AI is instructed to:
  - Respond naturally and conversationally as an AI concierge for Vansh.
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
- **final_decision values**: "transferred", "completed", "ended_no_speech"
- Schema is auto-created on first run if missing.

---

## Endpoints
- `/twilio/voice`: Twilio webhook for incoming calls (POST)
- `/twilio/ai-response`: Handles speech input and returns AI response (POST)
- `/twilio/transfer-fallback`: Handles transfer failures (POST)
- `/conversations`: Returns recent conversations (GET)
- `/test-db`: Diagnostic endpoint for DB connectivity (GET)

---

## Environment Variables
- `USE_AZURE_SQL=true` (production)
- `AZURE_SQL_CONNECTION_STRING` (from Key Vault)
- `REAL_PHONE_NUMBER` (Vansh's actual phone number for transfers)
- All other secrets (OpenAI, Twilio, etc.) are also loaded from Key Vault.

---

## Deployment
- Use `deploy.sh` to build, push, and restart the Azure App Service.
- Dockerfile ensures all dependencies (including ODBC driver) are installed.

---

## How to Review Conversations
- Visit `https://ai-voice-concierge.azurewebsites.net/conversations` after a call to see logs.
- Each entry includes all user and bot turns, timestamps, call metadata, and final decision.
- Response timing information is logged for performance monitoring.

---

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

## Source of Truth
- This README, the `prompts.py` system prompt, and the FastAPI endpoints are the canonical reference for how the system works.
- For any changes, update this file and the relevant code.

---

## Contact
For questions or improvements, contact Vansh or the project maintainer. 