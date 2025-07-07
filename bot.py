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

import openai
import json
import time
import logging
from config import AZURE_OPENAI_KEY, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_DEPLOYMENT
from prompts import get_system_prompt

# Initialize Azure OpenAI client with secure configuration
# Note: API keys are loaded from Azure Key Vault or environment variables
client = openai.AzureOpenAI(
    api_key=AZURE_OPENAI_KEY,
    api_version="2025-01-01-preview",
    azure_endpoint=AZURE_OPENAI_ENDPOINT
)

# Configure logging for the bot
logger = logging.getLogger("twilio")

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
        # Get the optimized system prompt for natural, fast responses
        system_prompt = get_system_prompt()
        
        # Build the complete message list for OpenAI API
        messages = [{"role": "system", "content": system_prompt}] + self.history
        
        # Time the OpenAI API call for performance monitoring
        openai_start = time.time()
        
        # Call Azure OpenAI API for response generation
        response = client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,  # Use configured deployment
            messages=messages,
            temperature=0.2,  # Slightly higher for more natural responses
            max_tokens=75,    # Limit for concise, natural responses
        )
        
        # Calculate and log API response time
        openai_time = (time.time() - openai_start) * 1000
        logger.info(f"OpenAI API call time: {openai_time:.2f}ms")
        
        # Extract the generated response
        reply = response.choices[0].message.content
        
        # Add the response to conversation history
        self.add_bot_message(reply)
        
        # Analyze the response for decision making
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
        # Get the specialized analysis prompt
        analysis_prompt = get_system_prompt() # This line was changed from get_urgency_analysis_prompt
        
        # Call Azure OpenAI for analysis
        response = client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            messages=[{"role": "user", "content": analysis_prompt}],
            temperature=0.1,  # Low temperature for consistent analysis
            max_tokens=200,   # Sufficient tokens for detailed analysis
        )
        
        try:
            # Parse the JSON response from the analysis
            analysis = json.loads(response.choices[0].message.content)
            return analysis
        except json.JSONDecodeError:
            # Fallback analysis if JSON parsing fails
            logger.warning("Failed to parse analysis response, using fallback")
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
            logger.info("Transfer decision detected in AI response")
        
        # Check for voicemail/end call decision
        elif "voicemail" in reply_lower or "message" in reply_lower:
            self.voicemail_decision = True
            logger.info("Voicemail decision detected in AI response")

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