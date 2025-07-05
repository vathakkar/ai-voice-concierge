import datetime
import pytz

def get_time_based_greeting():
    """Get appropriate greeting based on Pacific time"""
    pacific_tz = pytz.timezone('US/Pacific')
    pacific_time = datetime.datetime.now(pacific_tz)
    hour = pacific_time.hour
    
    if 5 <= hour < 12:
        return "Good morning"
    elif 12 <= hour < 17:
        return "Good afternoon"
    elif 17 <= hour < 21:
        return "Good evening"
    else:
        return "Good evening"  # Late night

def get_system_prompt():
    """Get the optimized system prompt for natural, fast AI responses"""
    return """You are Vansh's AI concierge. Respond naturally and conversationally in under 15 words.

URGENT & LEGITIMATE (deadlines, projects, emergencies):
"Let me connect you to Vansh right away. {TRANSFER}"

SPAM/SCAMS (warranties, sales, marketing):
"Sorry, Vansh isn't available right now. Please text if it's urgent. {END CALL}"

LOW PRIORITY:
"Vansh is busy at the moment. Could you text him instead? {END CALL}"

Be warm, natural, and conversational. Always include {TRANSFER} or {END CALL}."""

def get_urgency_analysis_prompt(user_response):
    """Get a prompt specifically for analyzing the urgency and legitimacy of a user's response"""
    return f"""Analyze this caller's response for urgency and legitimacy:

CALLER'S RESPONSE: "{user_response}"

Please evaluate:
1. URGENCY LEVEL (1-10): How time-sensitive is this matter?
2. LEGITIMACY: Is this a legitimate call for Vansh?
3. CALL TYPE: What category does this fall into?
4. RECOMMENDED ACTION: Transfer, voicemail, or end call?

Respond with a JSON format:
{{
    "urgency_level": <1-10>,
    "legitimacy": "legitimate" | "not_legitimate",
    "call_type": "family" | "business" | "sales" | "unknown" | "emergency",
    "reasoning": "<brief explanation>",
    "recommended_action": "transfer" | "voicemail" | "end_call"
}}""" 