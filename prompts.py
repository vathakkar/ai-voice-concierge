"""
AI Prompt Management for AI Voice Concierge
===========================================

This module contains the system prompts and prompt engineering logic for the AI Voice Concierge.
The prompts are carefully crafted to ensure natural, efficient, and consistent AI responses
for call screening and routing decisions.

Key Features:
- Time-based greeting generation
- Optimized system prompts for fast, natural responses
- Urgency analysis prompts for detailed call evaluation
- Consistent decision command formatting ({TRANSFER}, {END CALL})

Prompt Engineering Principles:
- Concise responses (under 15 words for main responses)
- Natural, conversational tone
- Clear decision commands for call routing
- Context-aware urgency assessment
- Consistent formatting for reliable parsing

Note: These prompts are the core of the AI's behavior and should be tested thoroughly
before deployment to ensure proper call screening and routing decisions.
"""

import datetime
import pytz

def get_time_based_greeting():
    """
    Get appropriate greeting based on Pacific time
    
    This function provides time-aware greetings to make the AI assistant
    sound more natural and contextually appropriate.
    
    Returns:
        str: Time-appropriate greeting (Good morning/afternoon/evening)
        
    Note: Uses Pacific timezone as the reference for greeting selection.
    """
    pacific_tz = pytz.timezone('US/Pacific')
    pacific_time = datetime.datetime.now(pacific_tz)
    hour = pacific_time.hour
    
    # Determine appropriate greeting based on time of day
    if 5 <= hour < 12:
        return "Good morning"
    elif 12 <= hour < 17:
        return "Good afternoon"
    elif 17 <= hour < 21:
        return "Good evening"
    else:
        return "Good evening"  # Late night (21:00 - 05:00)

def get_system_prompt():
    """
    Get the optimized system prompt for natural, fast AI responses
    
    This is the core system prompt that defines the AI's behavior and personality.
    It's designed for:
    - Fast response generation (~750ms average)
    - Natural, conversational tone
    - Clear decision making for call routing
    - Consistent formatting for reliable parsing
    
    The prompt includes specific instructions for:
    - Concise responses
    - Decision commands ({TRANSFER}, {END CALL})
    - Call type categorization (urgent, spam, low priority)
    - Natural language patterns
    - Anti-trolling and prank call detection
    
    Returns:
        str: The complete system prompt for Azure OpenAI
        
    Security Note: The prompt is designed to never reveal personal information
    and to maintain professional boundaries while being helpful.
    """
    return """You are Vansh's AI call screener. You only answer calls when Vansh is working or sleeping.

Use good judgment: Only transfer calls that are true emergencies or urgent personal or business matters. The caller must clearly explain why it is urgent. Just saying "it's urgent" is not enough.

Politely decline all other calls: Do not transfer them. Never take or promise to deliver a message. Instead, tell them to text Vansh directly if needed.

If the caller is trolling, joking, testing you, wasting time, or selling something: Respond with one short, witty but always polite line, then end the call. Never transfer them.

If the caller says something suspicious or threatening (like a scam): Stay calm and polite. Do not argue. Firmly decline and end the call. Never transfer them.

If the caller is unclear but not obviously trolling: Ask one polite follow-up question to find out exactly what they want. If they explain and it is truly urgent, transfer. If it is not urgent, tell them to text Vansh and end the call. If they stay vague, end the call.

Always be warm, polite, and professional: Use short, natural sentences. When giving a final answer, always end with {TRANSFER} or {END CALL}. Do not use {TRANSFER} or {END CALL} when asking a clarifying question — wait for their answer first.

When in doubt: Politely end the call. Vansh's time is the priority."""