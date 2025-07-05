# AI Voice Concierge - Source of Truth

## Overview
This project is a production-ready AI Voice Concierge system that answers phone calls, screens callers, and interacts using natural language. It is built with FastAPI, Twilio Voice, Azure OpenAI, and Azure SQL Database for persistent logging.

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
2. **Greeting**: The bot says "Hold one moment, please." and uses `<Gather input="speech">` to collect their reason for calling.
3. **AI Processing**: The caller's speech is sent to `/twilio/ai-response`, which uses Azure OpenAI to generate a response based on a detailed system prompt.
4. **Screening & Action**: The AI classifies the call and takes action:
   - **Transfer**: For legitimate/urgent calls, transfers to Vansh's real number
   - **Voicemail**: For sales/telemarketing, offers voicemail recording
   - **End Call**: For other cases, ends call after AI response
5. **Logging**: Every turn (user, bot, voicemail) is logged in the Azure SQL Database.
6. **Review**: Recent conversations can be viewed via the `/conversations` endpoint.

---

## AI Context (System Prompt)
- The AI is instructed to:
  - Greet professionally as an AI concierge for Vansh.
  - Screen for urgency, legitimacy, and call type (family, business, sales, etc.).
  - Transfer legitimate/urgent calls to Vansh's real number.
  - Offer voicemail for sales/telemarketing calls.
  - End calls appropriately based on the situation.
  - Never reveal personal information.
  - Log every interaction for review.
- The full system prompt is in `prompts.py` and is the source of truth for the AI's behavior.

---

## Call Handling Logic
- **Transfer Decision**: When AI response contains "transfer", call is transferred to `REAL_PHONE_NUMBER`
- **Voicemail Decision**: When AI response contains "voicemail" or "message", caller is prompted to leave a voicemail
- **Default**: Call ends after AI response for other scenarios
- **No Speech**: Call ends after retry attempts if no speech is detected

---

## Database Schema
- **calls**: One row per call (caller_id, start_time, end_time, final_decision)
- **conversation**: One row per turn (call_id, turn_index, speaker, text, timestamp)
- **final_decision values**: "transferred", "voicemail_left", "completed", "ended_no_speech"
- Schema is auto-created on first run if missing.

---

## Endpoints
- `/twilio/voice`: Twilio webhook for incoming calls (POST)
- `/twilio/ai-response`: Handles speech input and returns AI response (POST)
- `/twilio/voicemail`: Handles voicemail recording (POST)
- `/conversations`: Returns recent conversations (GET)
- `/voicemails`: Returns recent voicemails only (GET)
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
- Voicemail recordings are logged with URLs and duration.

## How to View Voicemails
- Visit `https://ai-voice-concierge.azurewebsites.net/voicemails` to see only voicemail messages.
- Each voicemail entry includes:
  - Caller ID
  - Timestamp
  - Voicemail details (recording URL and duration)
- Voicemail recordings are stored by Twilio and accessible via the provided URLs.

---

## Legacy/Unused Code
- All Azure Communication Services (ACS) logic and endpoints have been removed.
- Only Twilio, Azure OpenAI, and Azure SQL code remains.
- If you see any unused imports or functions, they can be safely deleted for clarity.

---

## Source of Truth
- This README, the `prompts.py` system prompt, and the FastAPI endpoints are the canonical reference for how the system works.
- For any changes, update this file and the relevant code.

---

## Contact
For questions or improvements, contact Vansh or the project maintainer. 