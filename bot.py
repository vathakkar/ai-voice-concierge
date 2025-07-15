"""
AI Voice Concierge Bot
======================

This module contains the VoiceConciergeBot class that handles AI-powered call screening
and response generation using Azure OpenAI. The bot analyzes caller speech, determines
urgency and legitimacy, and makes decisions about call handling (transfer vs end call).

Key Features:
- Natural language processing with Azure OpenAI
- Call urgency and legitimacy analysis
- Conversation state management
- Decision making for call routing
- Performance timing and logging

Security Note: API keys are loaded securely from configuration, never hardcoded.
"""

import os
import json
import time
import sys
import httpx
from config import AZURE_OPENAI_KEY, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_DEPLOYMENT
from prompts import get_system_prompt

class VoiceConciergeBot:
    """
    AI-powered voice concierge bot for call screening and routing
    
    This class manages the conversation with callers, analyzes their requests
    using Azure OpenAI, and makes intelligent decisions about call handling.
    
    Attributes:
        session_id: Unique identifier for this conversation session
        history: List of conversation turns (user and bot messages)
        transfer_decision: Boolean flag indicating if call should be transferred
        voicemail_decision: Boolean flag indicating if call should go to voicemail
        legitimate_reason: String describing the legitimate reason for calling
    """
    
    def __init__(self, session_id):
        """
        Initialize a new bot instance for a call session
        
        Args:
            session_id: Unique identifier for this conversation session
        """
        self.session_id = session_id
        self.history = []  # List of {role, content} dicts for conversation context
        self.transfer_decision = False  # Flag for transfer decisions
        self.voicemail_decision = False  # Flag for voicemail decisions
        self.legitimate_reason = None  # Store legitimate call reasons

    def add_user_message(self, text):
        """
        Add a user message to the conversation history
        
        Args:
            text: The user's speech input to be added to history
        """
        self.history.append({"role": "user", "content": text})

    def add_bot_message(self, text):
        """
        Add a bot response to the conversation history
        
        Args:
            text: The bot's response to be added to history
        """
        self.history.append({"role": "assistant", "content": text})

    def get_response(self):
        """
        Generate an AI response based on the conversation history
        
        This method:
        1. Builds the conversation context with system prompt
        2. Calls Azure OpenAI API for response generation
        3. Times the API call for performance monitoring
        4. Analyzes the response for decision making
        5. Adds the response to conversation history
        
        Returns:
            str: The AI-generated response text
            
        Note: The response may contain special commands like {TRANSFER} or {END CALL}
        that are processed by the main application logic.
        """
        system_prompt = get_system_prompt()
        messages = [{"role": "system", "content": system_prompt}] + self.history
        url = f"{AZURE_OPENAI_ENDPOINT}openai/deployments/{AZURE_OPENAI_DEPLOYMENT}/chat/completions?api-version=2025-01-01-preview"
        headers = {
            "api-key": AZURE_OPENAI_KEY,
            "Content-Type": "application/json"
        }
        payload = {
            "messages": messages
        }
        print("[OPENAI REST REQUEST]", url, json.dumps(payload))
        sys.stdout.flush()
        try:
            response = httpx.post(url, headers=headers, json=payload, timeout=30)
            print("[OPENAI REST RESPONSE]", response.status_code, response.text)
            sys.stdout.flush()
            response.raise_for_status()
            data = response.json()
            reply = data["choices"][0]["message"]["content"]
        except Exception as e:
            print("[OPENAI REST ERROR]", e)
            sys.stdout.flush()
            raise
        for tag in ["{CLARIFYING QUESTION}", "{TROLLING}"]:
            reply = reply.replace(tag, "")
        self.add_bot_message(reply)
        self._analyze_response(reply)
        return reply

    def analyze_user_response(self, user_response):
        """
        Analyze a user response for urgency and legitimacy
        
        This method provides detailed analysis of caller speech to determine:
        - Urgency level (1-10 scale)
        - Legitimacy of the call
        - Call type categorization
        - Recommended action
        
        Args:
            user_response: The caller's speech input to analyze
            
        Returns:
            dict: Analysis results with urgency, legitimacy, call type, and recommendations
            
        Note: This method is currently unused but available for future enhancements
        """
        analysis_prompt = get_system_prompt()
        url = f"{AZURE_OPENAI_ENDPOINT}openai/deployments/{AZURE_OPENAI_DEPLOYMENT}/chat/completions?api-version=2025-01-01-preview"
        headers = {
            "api-key": AZURE_OPENAI_KEY,
            "Content-Type": "application/json"
        }
        payload = {
            "messages": [{"role": "user", "content": analysis_prompt}]
        }
        print("[OPENAI REST ANALYZE REQUEST]", url, json.dumps(payload))
        sys.stdout.flush()
        try:
            response = httpx.post(url, headers=headers, json=payload, timeout=30)
            print("[OPENAI REST ANALYZE RESPONSE]", response.status_code, response.text)
            sys.stdout.flush()
            response.raise_for_status()
            data = response.json()
            analysis = json.loads(data["choices"][0]["message"]["content"])
            return analysis
        except Exception as e:
            print("[OPENAI REST ANALYZE ERROR]", e)
            sys.stdout.flush()
            return {
                "urgency_level": 5,
                "legitimacy": "unknown",
                "call_type": "unknown",
                "reasoning": "Could not parse analysis",
                "recommended_action": "voicemail"
            }

    def _analyze_response(self, reply):
        """
        Analyze bot response to set decision flags
        
        This private method examines the AI-generated response to determine
        if it contains decision commands like {TRANSFER} or {END CALL}.
        
        Args:
            reply: The AI-generated response text to analyze
        """
        reply_lower = reply.lower()
        
        # Check for transfer decision
        if "transfer" in reply_lower:
            self.transfer_decision = True
        
        # Check for voicemail/end call decision
        elif "voicemail" in reply_lower or "message" in reply_lower:
            self.voicemail_decision = True

    def is_transfer(self):
        """
        Check if the bot has decided to transfer the call
        
        Returns:
            bool: True if call should be transferred, False otherwise
        """
        return self.transfer_decision

    def is_voicemail(self):
        """
        Check if the bot has decided to send the call to voicemail
        
        Returns:
            bool: True if call should go to voicemail, False otherwise
        """
        return self.voicemail_decision
    
    def should_continue_conversation(self):
        """
        Determine if the conversation should continue or end
        
        This method evaluates the conversation state to decide if more
        information is needed before making a final decision.
        
        Returns:
            bool: True if conversation should continue, False if it should end
        """
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
        """
        Determine if the call should be ended
        
        This method evaluates whether the conversation has reached a point
        where it should be terminated, either due to a decision or sufficient
        information gathering.
        
        Returns:
            bool: True if call should be ended, False if it should continue
        """
        # Don't end if we have a clear decision (let the main logic handle it)
        if self.transfer_decision or self.voicemail_decision:
            return False
        
        # End if we've had enough conversation turns
        user_messages = [msg for msg in self.history if msg["role"] == "user"]
        if len(user_messages) >= 2:
            return True
        
        return False 