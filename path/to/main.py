import uuid
from fastapi import Request, Response
from fastapi.logger import logger

@app.post("/twilio/voice")
async def twilio_voice(request: Request):
    logger.info("/twilio/voice endpoint called")
    session_id = str(uuid.uuid4())
    bot = VoiceConciergeBot(session_id)
    sessions[session_id] = {"bot": bot, "turn_index": 0}
    logger.info(f"Started new session: {session_id}")
    action_url = f"/twilio/ai-response?session_id={session_id}&retry=0".replace("&", "&amp;")
    redirect_url = f"/twilio/ai-response?session_id={session_id}&retry=0".replace("&", "&amp;")
    twiml = f'''
    <Response>
        <Gather input="speech" action="{action_url}" method="POST" timeout="10">
            <Say voice="alice">Hello! Welcome to the AI Voice Concierge. How can I help you today?</Say>
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
            sessions[session_id] = {"bot": bot, "turn_index": 0}
        session = sessions[session_id]
        bot = session["bot"]
        turn_index = session["turn_index"]
        if user_speech.strip():
            bot.add_user_message(user_speech)
            ai_reply = bot.get_response()
            log_conversation_turn(session_id, turn_index, "user", user_speech)
            log_conversation_turn(session_id, turn_index, "bot", ai_reply)
            session["turn_index"] += 1
            logger.info(f"AI reply: {ai_reply}")
            action_url = f"/twilio/ai-response?session_id={session_id}&retry=0".replace("&", "&amp;")
            twiml = f'''
            <Response>
                <Say voice="alice">{ai_reply}</Say>
                <Gather input="speech" action="{action_url}" method="POST" timeout="10">
                    <Say voice="alice">Is there anything else I can help you with?</Say>
                </Gather>
                <Say voice="alice">Thank you for calling. Goodbye!</Say>
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