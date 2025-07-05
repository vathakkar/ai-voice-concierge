from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import StreamingResponse, JSONResponse, Response
from database import init_db, log_new_call, log_conversation_turn, log_final_decision, get_recent_conversations
from bot import VoiceConciergeBot
from config import REAL_PHONE_NUMBER
import uuid
import asyncio
import logging

app = FastAPI()

@app.on_event("startup")
def startup_event():
    init_db()

@app.get("/")
async def root():
    return {"message": "AI Voice Concierge is running! (Twilio mode)", "status": "healthy"}

sessions = {}
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("twilio")

# Twilio Voice Webhook Endpoint
@app.post("/twilio/voice")
async def twilio_voice(request: Request):
    logger.info("/twilio/voice endpoint called")
    session_id = str(uuid.uuid4())
    bot = VoiceConciergeBot(session_id)
    form = await request.form()
    caller_id = form.get("From", "unknown")
    call_id = log_new_call(caller_id)
    sessions[session_id] = {"bot": bot, "turn_index": 0, "call_id": call_id}
    logger.info(f"Started new session: {session_id} with call_id: {call_id}")
    action_url = f"/twilio/ai-response?session_id={session_id}&retry=0".replace("&", "&amp;")
    redirect_url = f"/twilio/ai-response?session_id={session_id}&retry=0".replace("&", "&amp;")
    twiml = f'''
    <Response>
        <Say voice="alice">Hello, this is an AI concierge for Vansh. How can I help you today?</Say>
        <Gather input="speech" action="{action_url}" method="POST" timeout="8">
        </Gather>
        <Redirect method="POST">{redirect_url}</Redirect>
    </Response>
    '''
    return Response(content=twiml, media_type="application/xml")

@app.post("/twilio/ai-response")
async def twilio_ai_response(request: Request):
    logger.info("/twilio/ai-response endpoint called")
    try:
        form = await request.form()
        logger.info(f"Incoming form data: {dict(form)}")
        user_speech = form.get("SpeechResult", "")
        session_id = request.query_params.get("session_id")
        retry = int(request.query_params.get("retry", "0"))
        logger.info(f"session_id: {session_id}, retry: {retry}, user_speech: '{user_speech}'")
        
        if not session_id or session_id not in sessions:
            logger.warning(f"Session ID {session_id} not found. Starting new session.")
            session_id = str(uuid.uuid4())
            bot = VoiceConciergeBot(session_id)
            caller_id = form.get("From", "unknown")
            call_id = log_new_call(caller_id)
            sessions[session_id] = {"bot": bot, "turn_index": 0, "call_id": call_id}
        
        session = sessions[session_id]
        bot = session["bot"]
        turn_index = session["turn_index"]
        call_id = session.get("call_id")
        
        if user_speech.strip():
            if call_id:
                log_conversation_turn(call_id, turn_index, "user", user_speech)
            bot.add_user_message(user_speech)
            ai_reply = bot.get_response()
            if call_id:
                log_conversation_turn(call_id, turn_index, "bot", ai_reply)
            session["turn_index"] += 1
            logger.info(f"AI reply: {ai_reply}")

            # Handle transfer and end call commands
            if "{TRANSFER}" in ai_reply:
                clean_reply = ai_reply.replace("{TRANSFER}", "").strip()
                logger.info("AI decided to transfer call")
                log_final_decision(call_id, "transferred")
                fallback_url = f"/twilio/transfer-fallback?session_id={session_id}".replace("&", "&amp;")
                twiml = f'''
                <Response>
                    <Say voice="alice">{clean_reply}</Say>
                    <Dial timeout="30" record="false" answerOnBridge="true" action="{fallback_url}">{REAL_PHONE_NUMBER}</Dial>
                </Response>
                '''
                return Response(content=twiml, media_type="application/xml")
            elif "{END CALL}" in ai_reply:
                clean_reply = ai_reply.replace("{END CALL}", "").strip()
                logger.info("AI decided to end call")
                log_final_decision(call_id, "completed")
                twiml = f'''
                <Response>
                    <Say voice="alice">{clean_reply}</Say>
                </Response>
                '''
                return Response(content=twiml, media_type="application/xml")
            else:
                logger.info("Continuing conversation")
                action_url = f"/twilio/ai-response?session_id={session_id}&retry=0".replace("&", "&amp;")
                redirect_url = f"/twilio/ai-response?session_id={session_id}&retry=0".replace("&", "&amp;")
                twiml = f'''
                <Response>
                    <Gather input="speech" action="{action_url}" method="POST" timeout="8">
                        <Say voice="alice">{ai_reply}</Say>
                    </Gather>
                    <Redirect method="POST">{redirect_url}</Redirect>
                </Response>
                '''
                return Response(content=twiml, media_type="application/xml")
        
        else:
            if retry == 0:
                logger.info("No speech detected, retrying once.")
                action_url = f"/twilio/ai-response?session_id={session_id}&retry=1".replace("&", "&amp;")
                redirect_url = f"/twilio/ai-response?session_id={session_id}&retry=1".replace("&", "&amp;")
                twiml = f'''
                <Response>
                    <Gather input="speech" action="{action_url}" method="POST" timeout="7">
                        <Say voice="alice">I didn't hear anything. Can you please say how I can help?</Say>
                    </Gather>
                    <Redirect method="POST">{redirect_url}</Redirect>
                </Response>
                '''
                return Response(content=twiml, media_type="application/xml")
            else:
                logger.info("No speech detected after retry, ending call.")
                if call_id:
                    log_final_decision(call_id, "ended_no_speech")
                twiml = '''
                <Response>
                    <Say voice="alice">Sorry, I still didn't hear anything. Goodbye!</Say>
                </Response>
                '''
                return Response(content=twiml, media_type="application/xml")
    
    except Exception as e:
        logger.error(f"Exception in /twilio/ai-response: {e}")
        twiml = '''
        <Response>
            <Say voice="alice">Sorry, there was an error. Goodbye!</Say>
        </Response>
        '''
        return Response(content=twiml, media_type="application/xml")

@app.post("/twilio/transfer-fallback")
async def twilio_transfer_fallback(request: Request):
    """Handle when transfer fails (phone busy, unavailable, etc.)"""
    logger.info("/twilio/transfer-fallback endpoint called")
    try:
        form = await request.form()
        session_id = request.query_params.get("session_id")
        dial_call_status = form.get("DialCallStatus", "unknown")
        
        logger.info(f"Transfer failed with status: {dial_call_status}")
        
        # Get call_id from session if available
        call_id = None
        if session_id and session_id in sessions:
            call_id = sessions[session_id].get("call_id")
        
        if call_id:
            log_final_decision(call_id, f"transfer_failed_{dial_call_status}")
        
        twiml = '''
        <Response>
            <Say voice="alice">Unfortunately Vansh is on another call. Please text him and he will get back to you as soon as possible.</Say>
        </Response>
        '''
        return Response(content=twiml, media_type="application/xml")
    
    except Exception as e:
        logger.error(f"Exception in /twilio/transfer-fallback: {e}")
        twiml = '''
        <Response>
            <Say voice="alice">Unfortunately Vansh is unavailable. Please text him and he will get back to you as soon as possible.</Say>
        </Response>
        '''
        return Response(content=twiml, media_type="application/xml")

@app.get("/conversations")
async def get_recent_conversations_endpoint(limit: int = 10):
    try:
        conversations = get_recent_conversations(limit)
        return {"conversations": conversations}
    except Exception as e:
        return {"error": str(e), "conversations": []}

@app.get("/test-db")
async def test_database():
    try:
        import os
        from config import SQLITE_DB_PATH
        USE_AZURE_SQL = os.getenv('USE_AZURE_SQL', 'false').lower() == 'true'
        AZURE_SQL_CONNECTION_STRING = os.getenv('AZURE_SQL_CONNECTION_STRING')
        if USE_AZURE_SQL and AZURE_SQL_CONNECTION_STRING:
            from database import get_connection
            conn = get_connection()
            c = conn.cursor()
            c.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE'")
            tables = c.fetchall()
            counts = {}
            for table in tables:
                table_name = table[0]
                c.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = c.fetchone()[0]
                counts[table_name] = count
            conn.close()
            return {
                "database_type": "Azure SQL Database",
                "tables": [table[0] for table in tables],
                "record_counts": counts
            }
        else:
            import sqlite3
            conn = sqlite3.connect(SQLITE_DB_PATH)
            c = conn.cursor()
            c.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = c.fetchall()
            counts = {}
            for table in tables:
                table_name = table[0]
                c.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = c.fetchone()[0]
                counts[table_name] = count
            conn.close()
            return {
                "database_type": "SQLite",
                "database_path": SQLITE_DB_PATH,
                "tables": [table[0] for table in tables],
                "record_counts": counts
            }
    except Exception as e:
        return {"error": str(e)} 