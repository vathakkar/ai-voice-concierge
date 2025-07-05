from fastapi import FastAPI, Request
from fastapi.responses import Response, JSONResponse
from database import init_db, log_new_call, log_conversation_turn, log_final_decision, get_recent_conversations
from bot import VoiceConciergeBot
from config import REAL_PHONE_NUMBER
import uuid
import logging

app = FastAPI()
logging.basicConfig(level=logging.INFO)
debug_logger = logging.getLogger("debug")

@app.on_event("startup")
def startup_event():
    init_db()

@app.get("/")
async def root():
    return {"message": "AI Voice Concierge is running! (Twilio mode)", "status": "healthy"}

sessions = {}

@app.post("/twilio/voice")
async def twilio_voice(request: Request):
    session_id = str(uuid.uuid4())
    bot = VoiceConciergeBot(session_id)
    form = await request.form()
    caller_id = form.get("From", "unknown")
    call_id = log_new_call(caller_id)
    sessions[session_id] = {"bot": bot, "turn_index": 0, "call_id": call_id}
    action_url = f"/twilio/ai-response?session_id={session_id}&retry=0".replace("&", "&amp;")
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
    try:
        form = await request.form()
        debug_logger.info(f"/twilio/ai-response form: {dict(form)}")
        user_speech = form.get("SpeechResult", "")
        debug_logger.info(f"/twilio/ai-response user_speech: '{user_speech}'")
        session_id = request.query_params.get("session_id")
        retry = int(request.query_params.get("retry", "0"))
        debug_logger.info(f"/twilio/ai-response session_id: {session_id}")
        debug_logger.info(f"/twilio/ai-response all session keys: {list(sessions.keys())}")
        if session_id in sessions:
            debug_logger.info(f"/twilio/ai-response session contents: {sessions[session_id]}")
        if not session_id or session_id not in sessions:
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
            if retry == 0:
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
                twiml = '''
                <Response>
                    <Say voice="polly.justin">Sorry, I still didn't hear anything. Goodbye!</Say>
                </Response>
                '''
                if call_id:
                    log_final_decision(call_id, "ended_no_speech")
                return Response(content=twiml, media_type="application/xml")
    except Exception as e:
        twiml = '''
        <Response>
            <Say voice="polly.justin">Sorry, there was an error. Goodbye!</Say>
        </Response>
        '''
        return Response(content=twiml, media_type="application/xml")

@app.post("/twilio/process-ai")
async def twilio_process_ai(request: Request):
    try:
        form = await request.form()
        debug_logger.info(f"/twilio/process-ai form: {dict(form)}")
        session_id = request.query_params.get("session_id")
        debug_logger.info(f"/twilio/process-ai session_id: {session_id}")
        debug_logger.info(f"/twilio/process-ai all session keys: {list(sessions.keys())}")
        if session_id in sessions:
            debug_logger.info(f"/twilio/process-ai session contents: {sessions[session_id]}")
        user_speech = None
        if session_id and session_id in sessions:
            session = sessions[session_id]
            user_speech = session.pop("pending_speech", None)
        debug_logger.info(f"/twilio/process-ai user_speech: '{user_speech}'")
        if not session_id or session_id not in sessions:
            twiml = '''
            <Response>
                <Say voice="polly.justin">Sorry, there was an error. Goodbye!</Say>
            </Response>
            '''
            return Response(content=twiml, media_type="application/xml")
        session = sessions[session_id]
        bot = session["bot"]
        turn_index = session["turn_index"]
        call_id = session.get("call_id")
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
        bot.add_user_message(user_speech)
        session["turn_index"] += 1
        ai_reply = bot.get_response()
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
        twiml = '''
        <Response>
            <Say voice="polly.justin">Sorry, there was an error. Goodbye!</Say>
        </Response>
        '''
        return Response(content=twiml, media_type="application/xml")

@app.post("/twilio/transfer-fallback")
async def twilio_transfer_fallback(request: Request):
    try:
        form = await request.form()
        session_id = request.query_params.get("session_id")
        dial_call_status = form.get("DialCallStatus", "unknown")
        call_id = None
        if session_id and session_id in sessions:
            call_id = sessions[session_id].get("call_id")
        if call_id:
            log_final_decision(call_id, f"transfer_failed_{dial_call_status}")
        twiml = '''
        <Response>
            <Say voice="polly.justin">Unfortunately Vansh is on another call. Please text him and he will get back to you as soon as possible.</Say>
        </Response>
        '''
        return Response(content=twiml, media_type="application/xml")
    except Exception:
        twiml = '''
        <Response>
            <Say voice="polly.justin">Unfortunately Vansh is unavailable. Please text him and he will get back to you as soon as possible.</Say>
        </Response>
        '''
        return Response(content=twiml, media_type="application/xml")

@app.get("/conversations")
async def get_recent_conversations_endpoint(limit: int = 10):
    return {"conversations": get_recent_conversations(limit)}

@app.get("/test-db")
async def test_database():
    return {"status": "Database connection successful"} 