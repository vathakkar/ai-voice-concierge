"""
Database Management for AI Voice Concierge
==========================================

This module handles all database operations for the AI Voice Concierge application.
It provides a unified interface for both Azure SQL Database (production) and SQLite (development),
with automatic schema creation and call/conversation logging.

Key Features:
- Dual database support (Azure SQL for production, SQLite for development)
- Automatic schema creation and migration
- Call and conversation logging
- Recent conversation retrieval
- Connection pooling and error handling

Database Schema:
- calls: Stores call metadata (caller_id, start_time, end_time, final_decision)
- conversation: Stores conversation turns (call_id, turn_index, speaker, text, timestamp)

Security Note: Database connection strings are loaded securely from Azure Key Vault
or environment variables, never hardcoded in the application.
"""

import os
import sqlite3
from datetime import datetime
from config import SQLITE_DB_PATH
import re

# Remove SQLite fallback logic and dependencies
# Only use Azure SQL (pyodbc) for all database operations

def get_connection():
    """
    Get a SQLite database connection (SQLite-only version)
    """
    return sqlite3.connect(SQLITE_DB_PATH)

def init_db():
    """
    Initialize the database and create tables if they don't exist
    
    This function creates the necessary database schema for both Azure SQL and SQLite.
    It uses database-specific SQL syntax to ensure compatibility.
    
    Schema Details:
    - calls table: Stores call metadata and final decisions
    - conversation table: Stores individual conversation turns with foreign key to calls
    - exception_phone_numbers table: Stores family/friends/favorite contacts that bypass AI screening
    
    Note: This function is called automatically on application startup.
    """
    conn = get_connection()
    c = conn.cursor()
    
    # Create calls table if it doesn't exist
    c.execute('''
        CREATE TABLE IF NOT EXISTS calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            caller_id TEXT,
            start_time TEXT,
            end_time TEXT,
            final_decision TEXT,
            summary TEXT,
            outcome TEXT
        )
    ''')
    
    # Create conversation table if it doesn't exist
    c.execute('''
        CREATE TABLE IF NOT EXISTS conversation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            call_id INTEGER,
            turn_index INTEGER,
            speaker TEXT,
            text TEXT,
            timestamp TEXT,
            FOREIGN KEY(call_id) REFERENCES calls(id)
        )
    ''')
    
    # Create exception_phone_numbers table if it doesn't exist
    c.execute('''
        CREATE TABLE IF NOT EXISTS exception_phone_numbers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_number TEXT UNIQUE,
            contact_name TEXT,
            category TEXT,
            added_date TEXT,
            is_active INTEGER DEFAULT 1
        )
    ''')
    
    # Remove T-SQL IF statements for adding columns; ensure all columns are present in CREATE TABLE
    # (No ALTER TABLE IF NOT EXISTS ... in SQLite)
    # The 'calls' table already includes 'summary' and 'outcome' columns in CREATE TABLE above.
    
    # Commit the schema changes
    conn.commit()
    conn.close()

def log_new_call(caller_id):
    """
    Log a new call and return its ID
    
    This function creates a new call record in the database and returns
    the call ID for future conversation logging.
    
    Args:
        caller_id: The phone number or identifier of the caller
        
    Returns:
        int: The database ID of the newly created call record
        
    Note: The start_time is automatically set to the current UTC time.
    """
    conn = get_connection()
    c = conn.cursor()
    
    # Record the call start time in ISO format
    start_time = datetime.utcnow().isoformat()
    
    # Azure SQL: Insert and get the generated ID
    c.execute('INSERT INTO calls (caller_id, start_time) VALUES (?, ?)', (caller_id, start_time))
    c.execute('SELECT SCOPE_IDENTITY()')
    
    # Get the call ID and return it
    call_id = c.fetchone()[0]
    conn.commit()
    conn.close()
    return int(call_id)

def log_conversation_turn(call_id, turn_index, speaker, text):
    """
    Log a conversation turn (user or bot message)
    
    This function records individual conversation turns in the database,
    linking them to the specific call via the call_id foreign key.
    
    Args:
        call_id: The database ID of the call this turn belongs to
        turn_index: The sequential index of this turn in the conversation
        speaker: Either 'user' or 'bot' to identify who spoke
        text: The actual text content of the message
        
    Note: The timestamp is automatically set to the current UTC time.
    """
    conn = get_connection()
    c = conn.cursor()
    
    # Record the conversation turn with current timestamp
    timestamp = datetime.utcnow().isoformat()
    c.execute('INSERT INTO conversation (call_id, turn_index, speaker, text, timestamp) VALUES (?, ?, ?, ?, ?)',
              (call_id, turn_index, speaker, text, timestamp))
    conn.commit()
    conn.close()

def log_final_decision(call_id, final_decision, summary=None, outcome=None):
    """
    Log the final decision and end time for a call
    
    This function updates the call record with the final outcome and end time.
    It's called when a call is completed, transferred, or ended.
    
    Args:
        call_id: The database ID of the call to update
        final_decision: The final outcome (e.g., 'transferred', 'completed', 'ended_no_speech')
        summary: Optional summary of the call
        outcome: Optional outcome of the call
        
    Note: The end_time is automatically set to the current UTC time.
    """
    conn = get_connection()
    c = conn.cursor()
    
    c.execute('''
        UPDATE calls SET end_time = ?, final_decision = ?, summary = ?, outcome = ? WHERE id = ?
    ''', (datetime.utcnow().isoformat(), final_decision, summary, outcome, call_id))
    conn.commit()
    conn.close()

def get_recent_conversations(limit=10):
    """
    Get recent conversations with full conversation history
    
    This function retrieves the most recent calls along with their complete
    conversation history, ordered by call start time (newest first).
    
    Args:
        limit: Maximum number of recent calls to return (default: 10)
        
    Returns:
        list: List of call objects with conversation history
        
    Example return structure:
    [
        {
            "call_id": 123,
            "caller_id": "+1234567890",
            "start_time": "2024-01-01T12:00:00",
            "end_time": "2024-01-01T12:02:30",
            "final_decision": "transferred",
            "conversation": [
                {"turn_index": 0, "speaker": "user", "text": "Hello", "timestamp": "..."},
                {"turn_index": 0, "speaker": "bot", "text": "Hi, how can I help?", "timestamp": "..."}
            ]
        }
    ]
    """
    conn = get_connection()
    c = conn.cursor()
    
    # Query to get recent calls with conversation details
    # Uses LEFT JOIN to include calls even if they have no conversation data
    c.execute('''
        SELECT 
            c.id as call_id,
            c.caller_id,
            c.start_time,
            c.end_time,
            c.final_decision,
            conv.turn_index,
            conv.speaker,
            conv.text,
            conv.timestamp
        FROM calls c
        LEFT JOIN conversation conv ON c.id = conv.call_id
        ORDER BY c.start_time DESC, conv.turn_index ASC
    ''')
    
    rows = c.fetchall()
    conn.close()
    
    # Group conversation turns by call
    conversations = {}
    for row in rows:
        call_id = row[0]
        
        # Create call object if it doesn't exist
        if call_id not in conversations:
            conversations[call_id] = {
                "call_id": call_id,
                "caller_id": row[1],
                "start_time": row[2],
                "end_time": row[3],
                "final_decision": row[4],
                "conversation": []
            }
        
        # Add conversation turn if it exists
        if row[5] is not None:  # If there's conversation data
            conversations[call_id]["conversation"].append({
                "turn_index": row[5],
                "speaker": row[6],
                "text": row[7],
                "timestamp": row[8]
            })
    
    # Convert to list and limit to requested number of calls
    result = list(conversations.values())[:limit]
    return result 

def normalize_phone_number(phone_number):
    """
    Normalize a phone number to E.164 format for US numbers.
    Strips all non-digit characters, ensures +1 prefix.
    """
    digits = re.sub(r'\D', '', phone_number)
    if digits.startswith('1') and len(digits) == 11:
        return f'+{digits}'
    elif len(digits) == 10:
        return f'+1{digits}'
    elif digits.startswith('+') and len(digits) > 1:
        return digits
    else:
        # fallback: just add plus if not present
        return '+' + digits

def is_exception_phone_number(phone_number):
    """
    Check if a phone number is in the exception list (family/friends/favorites)
    
    This function checks if the given phone number exists in the exception_phone_numbers
    table and is marked as active. If found, the call should bypass AI screening.
    
    Args:
        phone_number: The phone number to check (e.g., "+1234567890")
        
    Returns:
        dict or None: Contact information if found, None if not in exception list
        
    Note: Phone numbers are stored in E.164 format for consistency.
    """
    conn = get_connection()
    c = conn.cursor()
    normalized_number = normalize_phone_number(phone_number)
    c.execute('''
        SELECT id, phone_number, contact_name, category, added_date
        FROM exception_phone_numbers
        WHERE phone_number = ? AND is_active = 1
    ''', (normalized_number,))
    row = c.fetchone()
    conn.close()
    if row:
        return {
            'id': row[0],
            'phone_number': row[1],
            'contact_name': row[2],
            'category': row[3],
            'added_date': row[4]
        }
    return None

def add_exception_phone_number(phone_number, contact_name, category="family"):
    """
    Add a phone number to the exception list
    
    This function adds a new phone number to the exception_phone_numbers table.
    Calls from this number will bypass AI screening and be transferred directly.
    
    Args:
        phone_number: The phone number to add (e.g., "+1234567890")
        contact_name: Name of the contact (e.g., "Mom", "John Smith")
        category: Category of contact (e.g., "family", "friends", "work")
        
    Returns:
        bool: True if successfully added, False if already exists or error
        
    Note: Phone numbers are stored in E.164 format for consistency.
    """
    conn = get_connection()
    c = conn.cursor()
    normalized_number = normalize_phone_number(phone_number)
    c.execute('SELECT id FROM exception_phone_numbers WHERE phone_number = ?', (normalized_number,))
    if c.fetchone():
        conn.close()
        return False
    added_date = datetime.utcnow().isoformat()
    c.execute('''
        INSERT INTO exception_phone_numbers (phone_number, contact_name, category, added_date, is_active)
        VALUES (?, ?, ?, ?, 1)
    ''', (normalized_number, contact_name, category, added_date))
    conn.commit()
    conn.close()
    return True

def remove_exception_phone_number(phone_number):
    """
    Remove a phone number from the exception list (soft delete)
    
    This function marks a phone number as inactive in the exception_phone_numbers table.
    Calls from this number will no longer bypass AI screening.
    
    Args:
        phone_number: The phone number to remove (e.g., "+1234567890")
        
    Returns:
        bool: True if successfully removed, False if not found or error
        
    Note: This performs a soft delete by setting is_active = 0.
    """
    conn = get_connection()
    c = conn.cursor()
    normalized_number = normalize_phone_number(phone_number)
    c.execute('''
        UPDATE exception_phone_numbers 
        SET is_active = 0 
        WHERE phone_number = ?
    ''', (normalized_number,))
    rows_affected = c.rowcount
    conn.commit()
    conn.close()
    return rows_affected > 0

def get_all_exception_phone_numbers():
    """
    Get all active exception phone numbers
    
    This function retrieves all active phone numbers from the exception_phone_numbers table.
    
    Returns:
        list: List of dictionaries containing exception phone number data
        
    Note: Only returns active (is_active = 1) phone numbers.
    """
    conn = get_connection()
    c = conn.cursor()
    
    c.execute('''
        SELECT id, phone_number, contact_name, category, added_date
        FROM exception_phone_numbers
        WHERE is_active = 1
        ORDER BY contact_name ASC
    ''')
    
    rows = c.fetchall()
    conn.close()
    
    return [
        {
            'id': row[0],
            'phone_number': row[1],
            'contact_name': row[2],
            'category': row[3],
            'added_date': row[4]
        }
        for row in rows
    ] 

# Helper to update summary/outcome after call ends

def update_call_summary_and_outcome(call_id, summary, outcome):
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        UPDATE calls SET summary = ?, outcome = ? WHERE id = ?
    ''', (summary, outcome, call_id))
    conn.commit()
    conn.close() 

# Remove log_call_summary and all call_summaries table logic 