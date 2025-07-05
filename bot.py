import openai
import json
from config import AZURE_OPENAI_KEY, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_DEPLOYMENT
from prompts import get_system_prompt, get_urgency_analysis_prompt

# Set up OpenAI API for Azure (new 1.x API)
client = openai.AzureOpenAI(
    api_key=AZURE_OPENAI_KEY,
    api_version="2025-01-01-preview",
    azure_endpoint=AZURE_OPENAI_ENDPOINT
)

class VoiceConciergeBot:
    def __init__(self, session_id):
        self.session_id = session_id
        self.history = []  # List of {role, content} dicts
        self.transfer_decision = False
        self.voicemail_decision = False
        self.legitimate_reason = None

    def add_user_message(self, text):
        self.history.append({"role": "user", "content": text})

    def add_bot_message(self, text):
        self.history.append({"role": "assistant", "content": text})

    def get_response(self):
        # Use the new comprehensive system prompt
        system_prompt = get_system_prompt()
        messages = [{"role": "system", "content": system_prompt}] + self.history
        response = client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            messages=messages,
            temperature=0.2,  # Lower temperature for faster, more consistent responses
            max_tokens=200,   # Reduced for faster generation
        )
        reply = response.choices[0].message.content
        self.add_bot_message(reply)
        # Analyze the response for decision making
        self._analyze_response(reply)
        return reply

    def analyze_user_response(self, user_response):
        """Analyze user response for urgency and legitimacy"""
        analysis_prompt = get_urgency_analysis_prompt(user_response)
        response = client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            messages=[{"role": "user", "content": analysis_prompt}],
            temperature=0.1,
            max_tokens=200,
        )
        try:
            analysis = json.loads(response.choices[0].message.content)
            return analysis
        except json.JSONDecodeError:
            # Fallback analysis
            return {
                "urgency_level": 5,
                "legitimacy": "unknown",
                "call_type": "unknown",
                "reasoning": "Could not parse analysis",
                "recommended_action": "voicemail"
            }

    def _analyze_response(self, reply):
        """Analyze bot response to set decision flags"""
        reply_lower = reply.lower()
        if "transfer" in reply_lower:
            self.transfer_decision = True
        elif "voicemail" in reply_lower or "message" in reply_lower:
            self.voicemail_decision = True

    def is_transfer(self):
        return self.transfer_decision

    def is_voicemail(self):
        return self.voicemail_decision
    
    def should_continue_conversation(self):
        """Determine if the conversation should continue or end"""
        # If we have a clear decision, don't continue
        if self.transfer_decision or self.voicemail_decision:
            return False
        
        # If we have at least 2 exchanges (user -> bot -> user), we should have enough info
        user_messages = [msg for msg in self.history if msg["role"] == "user"]
        if len(user_messages) >= 2:
            return False
        
        # Continue if we're still gathering information
        return True
    
    def should_end_call(self):
        """Determine if the call should be ended"""
        # End if we have a clear decision
        if self.transfer_decision or self.voicemail_decision:
            return False
        
        # End if we've had enough conversation turns
        user_messages = [msg for msg in self.history if msg["role"] == "user"]
        if len(user_messages) >= 2:
            return True
        
        return False 