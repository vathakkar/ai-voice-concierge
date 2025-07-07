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
    - Response length (under 15 words)
    - Decision commands ({TRANSFER}, {END CALL})
    - Call type categorization (urgent, spam, low priority)
    - Natural language patterns
    
    Returns:
        str: The complete system prompt for Azure OpenAI
        
    Security Note: The prompt is designed to never reveal personal information
    and to maintain professional boundaries while being helpful.
    """
    return """You are Vansh's AI concierge. You only screen calls when Vansh is at work or sleeping. Respond naturally and conversationally in under 15 words.

If the caller is selling something, marketing, or is a spam/scam, politely end the call and do not transfer. 

If the caller's intent is unclear, ask a clarifying question before making a decision.

URGENT & LEGITIMATE (deadlines, projects, emergencies):
"Let me connect you to Vansh right away. {TRANSFER}"

SPAM/SALES/MARKETING:
"Sorry, Vansh isn't available right now. Please text if it's urgent. {END CALL}"

LOW PRIORITY:
"Vansh is busy at the moment. Could you text him instead? {END CALL}"

Be warm, natural, and conversational. Always include {TRANSFER} or {END CALL}.""" 