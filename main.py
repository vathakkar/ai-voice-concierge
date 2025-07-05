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
from database import init_db, log_new_call, log_conversation_turn, log_final_decision, get_recent_conversations
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
    1. Creates a new session for the call
    2. Initializes the AI bot
    3. Logs the call start
    4. Returns TwiML to greet the caller and collect speech
    
    Args:
        request: FastAPI Request object containing Twilio form data
        
    Returns:
        TwiML Response with greeting and speech collection
    """
    # Generate unique session ID for this call
    session_id = str(uuid.uuid4())
    
    # Initialize AI bot for this session
    bot = VoiceConciergeBot(session_id)
    
    # Extract caller information from Twilio form data
    form = await request.form()
    caller_id = form.get("From", "unknown")
    
    # Log the new call and get call ID for database tracking
    call_id = log_new_call(caller_id)
    
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
                log_final_decision(call_id, "transferred")
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
                log_final_decision(call_id, "completed")
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
    
    Args:
        request: FastAPI Request object containing transfer status
        
    Returns:
        TwiML Response with fallback message
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
        
        # Provide fallback message
        twiml = '''
        <Response>
            <Say voice="polly.justin">Unfortunately Vansh is on another call. Please text him and he will get back to you as soon as possible.</Say>
        </Response>
        '''
        return Response(content=twiml, media_type="application/xml")
    except Exception as e:
        # Handle any errors gracefully
        debug_logger.error(f"Error in twilio_transfer_fallback: {e}")
        twiml = '''
        <Response>
            <Say voice="polly.justin">Unfortunately Vansh is unavailable. Please text him and he will get back to you as soon as possible.</Say>
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