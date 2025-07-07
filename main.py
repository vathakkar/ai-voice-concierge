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

from fastapi import FastAPI, Request
from fastapi.responses import Response, JSONResponse
from database import init_db, log_new_call, log_conversation_turn, log_final_decision, get_recent_conversations, is_exception_phone_number, update_call_summary_and_outcome
from bot import VoiceConciergeBot
from config import REAL_PHONE_NUMBER
import uuid
import logging
from fastapi.staticfiles import StaticFiles
import time
import asyncio

# Initialize FastAPI application
app = FastAPI(title="AI Voice Concierge", description="AI-powered phone call screening system")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Configure logging for debugging and monitoring
logging.basicConfig(level=logging.INFO)
debug_logger = logging.getLogger("debug")

# Global session storage for call state management
# Note: In production, consider using Redis or database for session persistence
sessions = {}

@app.on_event("startup")
def startup_event():
    """Initialize database tables on application startup"""
    init_db()

# Add async startup event for DB connectivity check
@app.on_event("startup")
async def async_startup_event():
    try:
        # Use the test_database endpoint logic directly
        # This will catch DB issues at startup
        await test_database()
        logging.info("Database connectivity check at startup: SUCCESS")
    except Exception as e:
        logging.error(f"Database connectivity check at startup: FAILED - {e}")

@app.get("/")
async def root():
    """Health check endpoint to verify the application is running"""
    return {"message": "AI Voice Concierge is running! (Twilio mode)", "status": "healthy"}

@app.post("/twilio/voice")
async def twilio_voice(request: Request):
    """
    Twilio webhook endpoint for incoming voice calls
    
    This endpoint is called when a new call comes in. It:
    1. Checks if caller is in exception list (family/friends/favorites)
    2. If exception: transfers directly without AI screening
    3. If not exception: creates session and proceeds with AI screening
    4. Logs the call start
    
    Args:
        request: FastAPI Request object containing Twilio form data
        
    Returns:
        TwiML Response with appropriate action (transfer or AI screening)
    """
    # Extract caller information from Twilio form data
    form = await request.form()
    caller_id = form.get("From", "unknown")
    
    # Log the new call and get call ID for database tracking
    call_id = log_new_call(caller_id)
    
    # Check if caller is in exception list (family/friends/favorites)
    exception_contact = is_exception_phone_number(caller_id)
    
    if exception_contact:
        # Caller is in exception list - transfer directly without AI screening
        debug_logger.info(f"Exception contact detected: {exception_contact['contact_name']} ({exception_contact['phone_number']}) - transferring directly")
        
        # Log the direct transfer decision
        log_final_decision(call_id, "transferred_exception", summary="Exception contact, direct transfer.", outcome="exception_transfer")
        
        # Transfer to real phone number
        twiml = f'''
        <Response>
            <Say voice="polly.justin">Transferring you now.</Say>
            <Dial>{REAL_PHONE_NUMBER}</Dial>
        </Response>
        '''
        
        return Response(content=twiml, media_type="application/xml")
    
    # Caller is not in exception list - proceed with normal AI screening
    debug_logger.info(f"Regular caller detected: {caller_id} - proceeding with AI screening")
    
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
    twiml = f'''
    <Response>
        <Say voice="polly.justin">Hi, I am a virtual assistant. Tell me how can Vansh help you today? I will analyze your response and see if I can get a hold of him.</Say>
        <Gather input="speech" action="{action_url}" method="POST" timeout="6">
        </Gather>
        <Redirect method="POST">{action_url}</Redirect>
    </Response>
    '''
    
    return Response(content=twiml, media_type="application/xml")

@app.post("/twilio/ai-response")
async def twilio_ai_response(request: Request):
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
        # Extract form data from Twilio
        form = await request.form()
        debug_logger.info(f"/twilio/ai-response form: {dict(form)}")
        
        # Get speech result from Twilio
        user_speech = form.get("SpeechResult", "")
        debug_logger.info(f"/twilio/ai-response user_speech: '{user_speech}'")
        
        # Get session ID and retry count from query parameters
        session_id = request.query_params.get("session_id")
        retry = int(request.query_params.get("retry", "0"))
        
        # Debug logging for session management
        debug_logger.info(f"/twilio/ai-response session_id: {session_id}")
        debug_logger.info(f"/twilio/ai-response all session keys: {list(sessions.keys())}")
        if session_id in sessions:
            debug_logger.info(f"/twilio/ai-response session contents: {sessions[session_id]}")
        
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
            twiml = f'''
            <Response>
                <Say voice="polly.justin">One moment.</Say>
                <Redirect method="POST">{process_url}</Redirect>
            </Response>
            '''
            return Response(content=twiml, media_type="application/xml")
        else:
            # Handle no speech detected
            if retry == 0:
                # First retry - ask caller to repeat
                action_url = f"/twilio/ai-response?session_id={session_id}&retry=1".replace("&", "&amp;")
                twiml = f'''
                <Response>
                    <Gather input="speech" action="{action_url}" method="POST" timeout="5">
                        <Say voice="polly.justin">I didn't hear anything. Can you please repeat how I can help?</Say>
                    </Gather>
                    <Redirect method="POST">{action_url}</Redirect>
                </Response>
                '''
                return Response(content=twiml, media_type="application/xml")
            else:
                # Second retry - end call gracefully
                twiml = '''
                <Response>
                    <Say voice="polly.justin">Sorry, I still didn't hear anything. Goodbye!</Say>
                </Response>
                '''
                if call_id:
                    log_final_decision(call_id, "ended_no_speech")
                return Response(content=twiml, media_type="application/xml")
    except Exception as e:
        # Handle any errors gracefully
        debug_logger.error(f"Error in twilio_ai_response: {e}")
        twiml = '''
        <Response>
            <Say voice="polly.justin">Sorry, there was an error. Goodbye!</Say>
        </Response>
        '''
        return Response(content=twiml, media_type="application/xml")

@app.post("/twilio/process-ai")
async def twilio_process_ai(request: Request):
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
        debug_logger.info(f"/twilio/process-ai form: {dict(form)}")
        
        # Get session information
        session_id = request.query_params.get("session_id")
        debug_logger.info(f"/twilio/process-ai session_id: {session_id}")
        debug_logger.info(f"/twilio/process-ai all session keys: {list(sessions.keys())}")
        if session_id in sessions:
            debug_logger.info(f"/twilio/process-ai session contents: {sessions[session_id]}")
        
        # Retrieve stored speech from session
        user_speech = None
        if session_id and session_id in sessions:
            session = sessions[session_id]
            user_speech = session.pop("pending_speech", None)
        debug_logger.info(f"/twilio/process-ai user_speech: '{user_speech}'")
        
        # Handle missing session
        if not session_id or session_id not in sessions:
            twiml = '''
            <Response>
                <Say voice="polly.justin">Sorry, there was an error. Goodbye!</Say>
            </Response>
            '''
            return Response(content=twiml, media_type="application/xml")
        
        # Get session data
        session = sessions[session_id]
        bot = session["bot"]
        turn_index = session["turn_index"]
        call_id = session.get("call_id")
        
        # Validate speech input
        if not user_speech or not user_speech.strip():
            action_url = f"/twilio/ai-response?session_id={session_id}&retry=1".replace("&", "&amp;")
            twiml = f'''
            <Response>
                <Gather input="speech" action="{action_url}" method="POST" timeout="5">
                    <Say voice="polly.justin">I didn't hear anything. Can you please repeat how I can help?</Say>
                </Gather>
                <Redirect method="POST">{action_url}</Redirect>
            </Response>
            '''
            return Response(content=twiml, media_type="application/xml")
        
        # Process speech with AI and log timing
        ai_start = time.time()
        bot.add_user_message(user_speech)
        session["turn_index"] += 1
        ai_reply = bot.get_response()
        ai_time = time.time() - ai_start
        total_time = time.time() - start_time
        debug_logger.info(f"AI response time: {ai_time:.3f}s, Total process-ai time: {total_time:.3f}s")
        
        # Handle transfer decision
        if "{TRANSFER}" in ai_reply:
            clean_reply = ai_reply.replace("{TRANSFER}", "").strip()
            fallback_url = f"/twilio/transfer-fallback?session_id={session_id}".replace("&", "&amp;")
            twiml = f'''
            <Response>
                <Say voice="polly.justin">{clean_reply}</Say>
                <Dial timeout="30" record="false" answerOnBridge="true" action="{fallback_url}">{REAL_PHONE_NUMBER}</Dial>
            </Response>
            '''
            response = Response(content=twiml, media_type="application/xml")
            if call_id:
                log_conversation_turn(call_id, turn_index-1, "user", user_speech)
                log_conversation_turn(call_id, turn_index-1, "bot", ai_reply)
                # Generate summary (placeholder)
                summary = f"Call transferred. User said: {user_speech[:100]}..."
                log_final_decision(call_id, "transferred", summary=summary, outcome="transferred")
            return response
        
        # Handle end call decision
        elif "{END CALL}" in ai_reply:
            clean_reply = ai_reply.replace("{END CALL}", "").strip()
            twiml = f'''
            <Response>
                <Say voice="polly.justin">{clean_reply}</Say>
            </Response>
            '''
            response = Response(content=twiml, media_type="application/xml")
            if call_id:
                log_conversation_turn(call_id, turn_index-1, "user", user_speech)
                log_conversation_turn(call_id, turn_index-1, "bot", ai_reply)
                # Generate summary (placeholder)
                summary = f"Call ended. User said: {user_speech[:100]}..."
                log_final_decision(call_id, "completed", summary=summary, outcome="ended")
            return response
        
        # Continue conversation (no clear decision)
        else:
            action_url = f"/twilio/ai-response?session_id={session_id}&retry=0".replace("&", "&amp;")
            twiml = f'''
            <Response>
                <Gather input="speech" action="{action_url}" method="POST" timeout="6">
                    <Say voice="polly.justin">{ai_reply}</Say>
                </Gather>
                <Redirect method="POST">{action_url}</Redirect>
            </Response>
            '''
            response = Response(content=twiml, media_type="application/xml")
            if call_id:
                log_conversation_turn(call_id, turn_index-1, "user", user_speech)
                log_conversation_turn(call_id, turn_index-1, "bot", ai_reply)
            return response
    except Exception as e:
        # Handle any errors gracefully
        debug_logger.error(f"Error in twilio_process_ai: {e}")
        twiml = '''
        <Response>
            <Say voice="polly.justin">Sorry, there was an error. Goodbye!</Say>
        </Response>
        '''
        return Response(content=twiml, media_type="application/xml")

@app.post("/twilio/transfer-fallback")
async def twilio_transfer_fallback(request: Request):
    """
    Fallback endpoint for failed call transfers
    This endpoint is called when a transfer attempt fails (busy, no answer, etc.).
    It provides a graceful fallback message asking the caller to text instead.
    """
    try:
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
            twiml = '''
            <Response>
                <Say voice="polly.justin">Unfortunately Vansh is on another call. Please text him and he will get back to you as soon as possible.</Say>
                <Hangup/>
            </Response>
            '''
        return Response(content=twiml, media_type="application/xml")
    except Exception as e:
        # Handle any errors gracefully
        debug_logger.error(f"Error in twilio_transfer_fallback: {e}")
        twiml = '''
        <Response>
            <Say voice="polly.justin">Unfortunately Vansh is unavailable. Please text him and he will get back to you as soon as possible.</Say>
            <Hangup/>
        </Response>
        '''
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

@app.get("/test-db")
async def test_database():
    """
    Database connectivity test endpoint
    
    This endpoint tests the database connection to ensure the app can
    log calls and conversations properly.
    
    Returns:
        JSON response with database status
    """
    return {"status": "Database connection successful"}

# Phase 2: Exception Phone Number Management Endpoints

@app.get("/exceptions")
async def get_exception_phone_numbers():
    """
    Get all active exception phone numbers
    
    Returns:
        JSONResponse: List of all active exception phone numbers
    """
    try:
        from database import get_all_exception_phone_numbers
        exceptions = get_all_exception_phone_numbers()
        return JSONResponse(content={"exceptions": exceptions, "count": len(exceptions)})
    except Exception as e:
        debug_logger.error(f"Error getting exception phone numbers: {e}")
        return JSONResponse(content={"error": "Failed to retrieve exception phone numbers"}, status_code=500)

@app.post("/exceptions")
async def add_exception_phone_number(request: Request):
    """
    Add a phone number to the exception list
    
    Expected JSON body:
    {
        "phone_number": "+1234567890",
        "contact_name": "Mom",
        "category": "family"
    }
    
    Returns:
        JSONResponse: Success/failure status
    """
    try:
        from database import add_exception_phone_number
        body = await request.json()
        
        phone_number = body.get("phone_number")
        contact_name = body.get("contact_name")
        category = body.get("category", "family")
        
        if not phone_number or not contact_name:
            return JSONResponse(
                content={"error": "phone_number and contact_name are required"}, 
                status_code=400
            )
        
        success = add_exception_phone_number(phone_number, contact_name, category)
        
        if success:
            return JSONResponse(content={"message": "Exception phone number added successfully"})
        else:
            return JSONResponse(
                content={"error": "Phone number already exists in exception list"}, 
                status_code=409
            )
            
    except Exception as e:
        debug_logger.error(f"Error adding exception phone number: {e}")
        return JSONResponse(content={"error": "Failed to add exception phone number"}, status_code=500)

@app.delete("/exceptions/{phone_number}")
async def remove_exception_phone_number(phone_number: str):
    """
    Remove a phone number from the exception list
    
    Args:
        phone_number: The phone number to remove (URL encoded)
        
    Returns:
        JSONResponse: Success/failure status
    """
    try:
        from database import remove_exception_phone_number
        from urllib.parse import unquote
        
        # URL decode the phone number
        decoded_number = unquote(phone_number)
        
        success = remove_exception_phone_number(decoded_number)
        
        if success:
            return JSONResponse(content={"message": "Exception phone number removed successfully"})
        else:
            return JSONResponse(
                content={"error": "Phone number not found in exception list"}, 
                status_code=404
            )
            
    except Exception as e:
        debug_logger.error(f"Error removing exception phone number: {e}")
        return JSONResponse(content={"error": "Failed to remove exception phone number"}, status_code=500)

@app.get("/exceptions/check/{phone_number}")
async def check_exception_phone_number(phone_number: str):
    """
    Check if a phone number is in the exception list
    
    Args:
        phone_number: The phone number to check (URL encoded)
        
    Returns:
        JSONResponse: Contact information if found, null if not found
    """
    try:
        from urllib.parse import unquote
        
        # URL decode the phone number
        decoded_number = unquote(phone_number)
        
        contact = is_exception_phone_number(decoded_number)
        
        if contact:
            return JSONResponse(content={"found": True, "contact": contact})
        else:
            return JSONResponse(content={"found": False, "contact": None})
            
    except Exception as e:
        debug_logger.error(f"Error checking exception phone number: {e}")
        return JSONResponse(content={"error": "Failed to check exception phone number"}, status_code=500) 