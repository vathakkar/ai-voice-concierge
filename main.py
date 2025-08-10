"""
AI Voice Concierge - FastAPI Application
========================================

This is the main FastAPI application that handles Twilio webhooks for incoming phone calls.
The app provides an AI-powered voice concierge that screens calls and either transfers
urgent/legitimate calls or ends non-urgent calls with a text suggestion.

Key Features:
- Twilio webhook integration for voice calls
- AI-powered call screening using Azure OpenAI
- Session management for multi-turn conversations
- Database logging of all calls and conversations
- Transfer logic for urgent calls
- Fallback handling for failed transfers

Security Note: All API keys and secrets are loaded from Azure Key Vault in production
or environment variables in development. Never hardcode sensitive information.
"""

import os
import logging
import time
import uuid
import sys
from typing import Optional, Dict
from fastapi import FastAPI, Request, Depends, HTTPException, Form
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from twilio.request_validator import RequestValidator
from datetime import datetime

# Import our modules
from config import *
from database import *
from prompts import *
from tts_service import generate_tts_audio
from bot import VoiceConciergeBot

# Pre-generated audio cache for common messages
_pre_generated_audio: Dict[str, str] = {}

print("=== AI Concierge Clean Build 2025-01-15 ===")

# Initialize FastAPI application
app = FastAPI(title="AI Voice Concierge", description="AI-powered phone call screening system")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Global session storage for call state management
# Note: In production, consider using Redis or database for session persistence
sessions = {}

# Global audio file storage (in production, use Azure Blob Storage)
_audio_files: Dict[str, bytes] = {}

# Clear TTS cache on startup to ensure we use the new audio serving approach
def clear_tts_cache():
    """Clear TTS cache to ensure we use the new audio serving approach"""
    try:
        from tts_service import get_tts_service
        tts_service = get_tts_service()
        tts_service.clear_cache()
        logging.info("[TTS] Cleared TTS cache to ensure new audio serving approach")
    except Exception as e:
        logging.warning(f"[TTS] Could not clear TTS cache: {e}")

async def pre_generate_common_audio():
    """Pre-generate audio for common messages to improve performance"""
    if not ENABLE_TTS_PREGEN:
        logging.info("[TTS] TTS pre-generation disabled via ENABLE_TTS_PREGEN=false")
        return
        
    try:
        logging.info("[TTS] Pre-generating audio for common messages...")
        
        # List of common messages to pre-generate
        common_messages = [
            GREETING_MESSAGE,
            ONE_MOMENT_MESSAGE,
            RETRY_MESSAGE,
            FINAL_RETRY_MESSAGE,
            TRANSFER_MESSAGE,
            TRANSFER_FALLBACK_MESSAGE,
            ERROR_MESSAGE_ERR01,
            ERROR_MESSAGE_ERR02,
            ERROR_MESSAGE_ERR03
        ]
        
        for message in common_messages:
            try:
                audio_base64 = await generate_tts_audio(message)
                if audio_base64 and len(audio_base64) > 100:
                    _pre_generated_audio[message] = audio_base64
                    logging.info(f"[TTS] Pre-generated audio for: {message[:50]}...")
                else:
                    logging.warning(f"[TTS] Failed to pre-generate audio for: {message[:50]}...")
            except Exception as e:
                logging.warning(f"[TTS] Error pre-generating audio for '{message[:30]}...': {e}")
        
        logging.info(f"[TTS] Pre-generated {len(_pre_generated_audio)} common audio files")
    except Exception as e:
        logging.error(f"[TTS] Error in pre-generate_common_audio: {e}")

# Clear cache on module import
clear_tts_cache()

@app.get("/audio/{audio_id}")
async def serve_audio(audio_id: str):
    """Serve audio files for Twilio"""
    if audio_id in _audio_files:
        audio_data = _audio_files[audio_id]
        # Clean up old audio files (older than 5 minutes)
        _cleanup_old_audio_files()
        return Response(content=audio_data, media_type="audio/wav")
    else:
        raise HTTPException(status_code=404, detail="Audio file not found")

def _cleanup_old_audio_files():
    """Clean up old audio files to prevent memory issues"""
    global _audio_files
    # In a real implementation, you'd track timestamps
    # For now, just limit the cache size
    if len(_audio_files) > 100:
        # Remove oldest entries (simple implementation)
        keys_to_remove = list(_audio_files.keys())[:50]
        for key in keys_to_remove:
            del _audio_files[key]

async def create_tts_twiml(text: str, fallback_to_twilio: bool = True) -> str:
    """
    Create TwiML with Azure TTS audio, falling back to Twilio TTS if needed
    
    Args:
        text: Text to synthesize
        fallback_to_twilio: Whether to fallback to Twilio TTS if Azure fails
        
    Returns:
        TwiML string with custom audio or fallback to Twilio Say
    """
    if not text or not text.strip():
        logging.warning("[TTS] Empty text provided to create_tts_twiml")
        return '''
        <Response>
            <Say voice="polly.justin">I'm sorry, there was an error processing your request.</Say>
        </Response>
        '''
    
    try:
        # Check if we have pre-generated audio for this text
        if text in _pre_generated_audio:
            logging.info(f"[TTS] Using pre-generated audio for: {text[:50]}...")
            audio_base64 = _pre_generated_audio[text]
        else:
            # Try Azure TTS first
            audio_base64 = await generate_tts_audio(text)
        
        if audio_base64 and len(audio_base64) > 100:  # Ensure we have valid audio data
            logging.info(f"[TTS] Using Azure TTS for: {text[:50]}...")
            
            # Decode base64 to get audio data
            import base64
            audio_data = base64.b64decode(audio_base64)
            
            # Store audio data with unique ID
            audio_id = str(uuid.uuid4())
            _audio_files[audio_id] = audio_data
            
            # Create audio URL
            audio_url = f"https://ai-voice-concierge-canadacentral.azurewebsites.net/audio/{audio_id}"
            
            return f'''
            <Response>
                <Play>{audio_url}</Play>
            </Response>
            '''
        else:
            logging.warning(f"[TTS] Azure TTS returned invalid audio data, falling back to Twilio TTS")
    except Exception as e:
        logging.error(f"[TTS] Azure TTS failed in create_tts_twiml: {str(e)}")
    
    # Fallback to Twilio TTS if Azure fails or fallback is enabled
    if fallback_to_twilio:
        logging.info(f"[TTS] Using Twilio TTS fallback for: {text[:50]}...")
        return f'''
        <Response>
            <Say voice="polly.justin">{text}</Say>
        </Response>
        '''
    else:
        return f'''
        <Response>
            <Say voice="polly.justin">{text}</Say>
        </Response>
        '''

async def create_tts_twiml_with_gather(text: str, action_url: str, timeout: int = 6, fallback_to_twilio: bool = True) -> str:
    """
    Create TwiML with Azure TTS audio and Gather element
    
    Args:
        text: Text to synthesize
        action_url: URL for Gather action
        timeout: Speech timeout in seconds
        fallback_to_twilio: Whether to fallback to Twilio TTS if Azure fails
        
    Returns:
        TwiML string with custom audio and Gather
    """
    if not text or not text.strip():
        logging.warning("[TTS] Empty text provided to create_tts_twiml_with_gather")
        return f'''
        <Response>
            <Say voice="polly.justin">I'm sorry, there was an error processing your request.</Say>
            <Gather input="speech" action="{action_url}" method="POST" timeout="{timeout}">
            </Gather>
            <Redirect method="POST">{action_url}</Redirect>
        </Response>
        '''
    
    try:
        # Check if we have pre-generated audio for this text
        if text in _pre_generated_audio:
            logging.info(f"[TTS] Using pre-generated audio with Gather for: {text[:50]}...")
            audio_base64 = _pre_generated_audio[text]
        else:
            # Try Azure TTS first
            audio_base64 = await generate_tts_audio(text)
        
        if audio_base64 and len(audio_base64) > 100:  # Ensure we have valid audio data
            logging.info(f"[TTS] Using Azure TTS with Gather for: {text[:50]}...")
            
            # Decode base64 to get audio data
            import base64
            audio_data = base64.b64decode(audio_base64)
            
            # Store audio data with unique ID
            audio_id = str(uuid.uuid4())
            _audio_files[audio_id] = audio_data
            
            # Create audio URL
            audio_url = f"https://ai-voice-concierge-canadacentral.azurewebsites.net/audio/{audio_id}"
            
            return f'''
            <Response>
                <Play>{audio_url}</Play>
                <Gather input="speech" action="{action_url}" method="POST" timeout="{timeout}">
                </Gather>
                <Redirect method="POST">{action_url}</Redirect>
            </Response>
            '''
        else:
            logging.warning(f"[TTS] Azure TTS returned invalid audio data, falling back to Twilio TTS")
    except Exception as e:
        logging.error(f"[TTS] Azure TTS failed in create_tts_twiml_with_gather: {str(e)}")
    
    # Fallback to Twilio TTS if Azure fails or fallback is enabled
    if fallback_to_twilio:
        logging.info(f"[TTS] Using Twilio TTS fallback with Gather for: {text[:50]}...")
        return f'''
        <Response>
            <Say voice="polly.justin">{text}</Say>
            <Gather input="speech" action="{action_url}" method="POST" timeout="{timeout}">
            </Gather>
            <Redirect method="POST">{action_url}</Redirect>
        </Response>
        '''
    else:
        return f'''
        <Response>
            <Say voice="polly.justin">{text}</Say>
            <Gather input="speech" action="{action_url}" method="POST" timeout="{timeout}">
            </Gather>
            <Redirect method="POST">{action_url}</Redirect>
        </Response>
        '''

@app.on_event("startup")
async def startup_event():
    """Initialize database tables and pre-generate common audio on application startup"""
    init_db()
    await pre_generate_common_audio()

@app.get("/")
async def root():
    """Health check endpoint to verify the application is running"""
    return {"message": "AI Voice Concierge is running! (Twilio mode)", "status": "healthy"}

async def verify_twilio_request(request: Request):
    validator = RequestValidator(TWILIO_AUTH_TOKEN)
    url = str(request.url)
    # Use X-Forwarded-Proto if present to reconstruct the original URL
    forwarded_proto = request.headers.get("x-forwarded-proto")
    if forwarded_proto and url.startswith("http://"):
        url = url.replace("http://", f"{forwarded_proto}://", 1)
    logging.info(f"[DEBUG] Twilio signature validation URL: {url}")
    form = await request.form()
    params = dict(form)
    signature = request.headers.get("X-Twilio-Signature", "")
    logging.info(f"[DEBUG] Signature from header: {signature}")
    logging.info(f"[DEBUG] Params: {params}")
    if not validator.validate(url, params, signature):
        logging.info("[DEBUG] Signature validation failed!")
        raise HTTPException(status_code=403, detail="Request signature invalid")
    logging.info("[DEBUG] Signature validation succeeded.")

@app.post("/twilio/voice")
async def twilio_voice(request: Request, _=Depends(verify_twilio_request)):
    start = time.time()
    # Extract caller information from Twilio form data
    form = await request.form()
    caller_id = form.get("From", "unknown")
    
    # Log the new call and get call ID for database tracking
    call_id = log_new_call(caller_id)
    
    # Check if caller is in exception list (family/friends/favorites)
    exception_contact = is_exception_phone_number(caller_id)
    
    if exception_contact:
        logging.info("[TTS] Exception contact, using TTS for transfer message.")
        # Caller is in exception list - transfer directly without AI screening
        log_final_decision(call_id, "transferred_exception", summary="Exception contact, direct transfer.", outcome="exception_transfer")
        # Transfer to real phone number
        twiml = await create_tts_twiml(TRANSFER_MESSAGE)
        twiml = twiml.replace('</Response>', f'<Dial>{REAL_PHONE_NUMBER}</Dial></Response>')
        logging.info(f"[TTS] TwiML returned: {twiml[:300]}")
        logging.info(f"[TTS] /twilio/voice latency: {time.time() - start:.2f}s")
        return Response(content=twiml, media_type="application/xml")
    
    # Caller is not in exception list - proceed with normal AI screening
    
    # Generate unique session ID for this call
    session_id = str(uuid.uuid4())
    
    # Initialize AI bot for this session
    bot = VoiceConciergeBot(session_id)
    
    # Store session data for later use
    sessions[session_id] = {
        "bot": bot, 
        "turn_index": 0, 
        "call_id": call_id
    }
    
    # Create URL for the next step (speech processing)
    # Note: &amp; is used to escape & in XML
    action_url = f"/twilio/ai-response?session_id={session_id}&retry=0".replace("&", "&amp;")
    
    # Generate TwiML response with greeting and speech collection
    twiml = await create_tts_twiml_with_gather(GREETING_MESSAGE, action_url, timeout=3)
    logging.info(f"[TTS] TwiML returned: {twiml[:300]}")
    logging.info(f"[TTS] /twilio/voice latency: {time.time() - start:.2f}s")
    return Response(content=twiml, media_type="application/xml")

@app.post("/twilio/ai-response")
async def twilio_ai_response(request: Request, _=Depends(verify_twilio_request)):
    """
    Twilio webhook endpoint for processing speech input
    
    This endpoint handles the speech collected from the caller. It:
    1. Extracts speech from Twilio form data
    2. Manages session state
    3. Handles retry logic for no-speech scenarios
    4. Routes to AI processing if speech is detected
    
    Args:
        request: FastAPI Request object containing Twilio form data
        
    Returns:
        TwiML Response with appropriate next action
    """
    try:
        start_time = time.time()
        form = await request.form()
        
        # Get speech result from Twilio
        user_speech = form.get("SpeechResult", "")
        
        # Get session ID and retry count from query parameters
        session_id = request.query_params.get("session_id")
        retry = int(request.query_params.get("retry", "0"))
        
        # Handle missing or invalid session by creating a new one
        if not session_id or session_id not in sessions:
            session_id = str(uuid.uuid4())
            bot = VoiceConciergeBot(session_id)
            caller_id = form.get("From", "unknown")
            call_id = log_new_call(caller_id)
            sessions[session_id] = {"bot": bot, "turn_index": 0, "call_id": call_id}
        
        # Get session data
        session = sessions[session_id]
        bot = session["bot"]
        turn_index = session["turn_index"]
        call_id = session.get("call_id")
        
        # Check if speech was detected
        if user_speech.strip():
            # Store speech for processing and redirect to AI processing
            session["pending_speech"] = user_speech
            process_url = f"/twilio/process-ai?session_id={session_id}".replace("&", "&amp;")
            twiml = await create_tts_twiml(ONE_MOMENT_MESSAGE)
            twiml = twiml.replace('</Response>', f'<Redirect method="POST">{process_url}</Redirect></Response>')
            logging.info(f"[TTS] TwiML returned: {twiml[:300]}")
            logging.info(f"[TTS] /twilio/ai-response latency: {time.time() - start_time:.2f}s")
            return Response(content=twiml, media_type="application/xml")
        else:
            # Handle no speech detected
            if retry == 0:
                # First retry - ask caller to repeat
                action_url = f"/twilio/ai-response?session_id={session_id}&retry=1".replace("&", "&amp;")
                twiml = await create_tts_twiml_with_gather(RETRY_MESSAGE, action_url, timeout=5)
                logging.info(f"[TTS] TwiML returned: {twiml[:300]}")
                logging.info(f"[TTS] /twilio/ai-response latency: {time.time() - start_time:.2f}s")
                return Response(content=twiml, media_type="application/xml")
            else:
                # Second retry - end call gracefully
                twiml = await create_tts_twiml(FINAL_RETRY_MESSAGE)
                if call_id:
                    log_final_decision(call_id, "ended_no_speech")
                logging.info(f"[TTS] TwiML returned: {twiml[:300]}")
                logging.info(f"[TTS] /twilio/ai-response latency: {time.time() - start_time:.2f}s")
                return Response(content=twiml, media_type="application/xml")
    except Exception as e:
        # Handle any errors gracefully
        twiml = '''
        <Response>
            <Say voice="polly.justin">{ERROR_MESSAGE_ERR01}</Say>
        </Response>
        '''
        logging.info(f"[TTS] TwiML returned: {twiml[:300]}")
        logging.info(f"[TTS] /twilio/ai-response latency: {time.time() - start_time:.2f}s")
        return Response(content=twiml, media_type="application/xml")

@app.post("/twilio/process-ai")
async def twilio_process_ai(request: Request, _=Depends(verify_twilio_request)):
    """
    AI processing endpoint for speech analysis and response generation
    
    This endpoint processes the collected speech using Azure OpenAI to:
    1. Analyze the caller's request
    2. Generate an appropriate response
    3. Make transfer/end call decisions
    4. Log the conversation
    
    Args:
        request: FastAPI Request object
        
    Returns:
        TwiML Response with AI-generated response and next action
    """
    try:
        start_time = time.time()
        form = await request.form()
        session_id = request.query_params.get("session_id")
        user_speech = None
        if session_id and session_id in sessions:
            session = sessions[session_id]
            user_speech = session.pop("pending_speech", None)
        if not session_id or session_id not in sessions:
            twiml = await create_tts_twiml(ERROR_MESSAGE_ERR02)
            logging.info(f"[TTS] TwiML returned: {twiml[:300]}")
            logging.info(f"[TTS] /twilio/process-ai latency: {time.time() - start_time:.2f}s")
            return Response(content=twiml, media_type="application/xml")
        session = sessions[session_id]
        bot = session["bot"]
        turn_index = session["turn_index"]
        call_id = session.get("call_id")
        if not user_speech or not user_speech.strip():
            action_url = f"/twilio/ai-response?session_id={session_id}&retry=1".replace("&", "&amp;")
            twiml = await create_tts_twiml_with_gather(RETRY_MESSAGE, action_url, timeout=5)
            logging.info(f"[TTS] TwiML returned: {twiml[:300]}")
            logging.info(f"[TTS] /twilio/process-ai latency: {time.time() - start_time:.2f}s")
            return Response(content=twiml, media_type="application/xml")
        try:
            ai_start = time.time()
            bot.add_user_message(user_speech)
            session["turn_index"] += 1
            ai_reply = bot.get_response()
            ai_time = time.time() - ai_start
            total_time = time.time() - start_time
            logging.info(f"[DEBUG] AI response time: {ai_time}, Total process-ai time: {total_time}")
        except Exception as ai_e:
            twiml = await create_tts_twiml(ERROR_MESSAGE_ERR02)
            logging.info(f"[TTS] TwiML returned: {twiml[:300]}")
            logging.info(f"[TTS] /twilio/process-ai latency: {time.time() - start_time:.2f}s")
            return Response(content=twiml, media_type="application/xml")
        if "{TRANSFER}" in ai_reply:
            clean_reply = ai_reply.replace("{TRANSFER}", "").strip()
            fallback_url = f"/twilio/transfer-fallback?session_id={session_id}".replace("&", "&amp;")
            twiml = await create_tts_twiml(clean_reply)
            twiml = twiml.replace('</Response>', f'<Dial timeout="30" record="false" answerOnBridge="true" action="{fallback_url}">{REAL_PHONE_NUMBER}</Dial></Response>')
            response = Response(content=twiml, media_type="application/xml")
            if call_id:
                log_conversation_turn(call_id, turn_index-1, "user", user_speech)
                log_conversation_turn(call_id, turn_index-1, "bot", ai_reply)
                summary = f"Call transferred. User said: {user_speech[:100]}..."
                log_final_decision(call_id, "transferred", summary=summary, outcome="transferred")
            logging.info(f"[TTS] TwiML returned: {twiml[:300]}")
            logging.info(f"[TTS] /twilio/process-ai latency: {time.time() - start_time:.2f}s")
            return response
        elif "{END CALL}" in ai_reply:
            clean_reply = ai_reply.replace("{END CALL}", "").strip()
            twiml = await create_tts_twiml(clean_reply)
            response = Response(content=twiml, media_type="application/xml")
            if call_id:
                log_conversation_turn(call_id, turn_index-1, "user", user_speech)
                log_conversation_turn(call_id, turn_index-1, "bot", ai_reply)
                summary = f"Call ended. User said: {user_speech[:100]}..."
                log_final_decision(call_id, "completed", summary=summary, outcome="ended")
            logging.info(f"[TTS] TwiML returned: {twiml[:300]}")
            logging.info(f"[TTS] /twilio/process-ai latency: {time.time() - start_time:.2f}s")
            return response
        else:
            action_url = f"/twilio/ai-response?session_id={session_id}&retry=0".replace("&", "&amp;")
            twiml = await create_tts_twiml_with_gather(ai_reply, action_url, timeout=3)
            response = Response(content=twiml, media_type="application/xml")
            if call_id:
                log_conversation_turn(call_id, turn_index-1, "user", user_speech)
                log_conversation_turn(call_id, turn_index-1, "bot", ai_reply)
            logging.info(f"[TTS] TwiML returned: {twiml[:300]}")
            logging.info(f"[TTS] /twilio/process-ai latency: {time.time() - start_time:.2f}s")
            return response
    except Exception as e:
        twiml = '''
        <Response>
            <Say voice="polly.justin">{ERROR_MESSAGE_ERR02}</Say>
        </Response>
        '''
        logging.info(f"[TTS] TwiML returned: {twiml[:300]}")
        logging.info(f"[TTS] /twilio/process-ai latency: {time.time() - start_time:.2f}s")
        return Response(content=twiml, media_type="application/xml")

@app.post("/twilio/transfer-fallback")
async def twilio_transfer_fallback(request: Request):
    """
    Fallback endpoint for failed call transfers
    This endpoint is called when a transfer attempt fails (busy, no answer, etc.).
    It provides a graceful fallback message asking the caller to text instead.
    """
    try:
        start_time = time.time()
        form = await request.form()
        session_id = request.query_params.get("session_id")
        dial_call_status = form.get("DialCallStatus", "unknown")
        
        # Log the transfer failure
        call_id = None
        if session_id and session_id in sessions:
            call_id = sessions[session_id].get("call_id")
        if call_id:
            log_final_decision(call_id, f"transfer_failed_{dial_call_status}")
        
        # Only play fallback message if transfer failed
        if dial_call_status == "completed":
            # Call was answered and completed normally
            twiml = '''
            <Response>
                <Hangup/>
            </Response>
            '''
        else:
            # Transfer failed (busy, no answer, etc.)
            fallback_text = TRANSFER_FALLBACK_MESSAGE
            twiml = await create_tts_twiml(fallback_text)
            twiml = twiml.replace('</Response>', '<Hangup/></Response>')
        logging.info(f"[TTS] TwiML returned: {twiml[:300]}")
        logging.info(f"[TTS] /twilio/transfer-fallback latency: {time.time() - start_time:.2f}s")
        return Response(content=twiml, media_type="application/xml")
    except Exception as e:
        # Handle any errors gracefully
        error_text = ERROR_MESSAGE_ERR03
        twiml = await create_tts_twiml(error_text)
        twiml = twiml.replace('</Response>', '<Hangup/></Response>')
        logging.info(f"[TTS] TwiML returned: {twiml[:300]}")
        logging.info(f"[TTS] /twilio/transfer-fallback latency: {time.time() - start_time:.2f}s")
        return Response(content=twiml, media_type="application/xml")

@app.get("/conversations")
async def get_recent_conversations_endpoint(limit: int = 10):
    """
    API endpoint to retrieve recent call conversations
    
    This endpoint allows reviewing recent calls and their conversation history.
    Useful for monitoring call quality and AI performance.
    
    Args:
        limit: Maximum number of recent calls to return (default: 10)
        
    Returns:
        JSON response with conversation data
    """
    return {"conversations": get_recent_conversations(limit)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000) 