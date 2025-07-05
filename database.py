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
from config import SQLITE_DB_PATH, AZURE_SQL_CONNECTION_STRING

# Database configuration - determines which database to use
# Set USE_AZURE_SQL=true in production, false for local development
USE_AZURE_SQL = os.getenv('USE_AZURE_SQL', 'false').lower() == 'true'

def get_connection():
    """
    Get database connection based on configuration
    
    This function automatically selects the appropriate database:
    - Production: Azure SQL Database with connection string from Key Vault
    - Development: Local SQLite database
    
    Returns:
        Database connection object (pyodbc for Azure SQL, sqlite3 for SQLite)
        
    Raises:
        Exception: If connection cannot be established
    """
    if USE_AZURE_SQL and AZURE_SQL_CONNECTION_STRING:
        try:
            # Production: Use Azure SQL Database
            import pyodbc
            return pyodbc.connect(AZURE_SQL_CONNECTION_STRING)
        except ImportError:
            # Fallback to SQLite if pyodbc is not installed
            print("Warning: pyodbc not installed, falling back to SQLite")
            return sqlite3.connect(SQLITE_DB_PATH)
    else:
        # Development: Use local SQLite database
        return sqlite3.connect(SQLITE_DB_PATH)

def init_db():
    """
    Initialize the database and create tables if they don't exist
    
    This function creates the necessary database schema for both Azure SQL and SQLite.
    It uses database-specific SQL syntax to ensure compatibility.
    
    Schema Details:
    - calls table: Stores call metadata and final decisions
    - conversation table: Stores individual conversation turns with foreign key to calls
    
    Note: This function is called automatically on application startup.
    """
    conn = get_connection()
    c = conn.cursor()
    
    if USE_AZURE_SQL and AZURE_SQL_CONNECTION_STRING:
        # Azure SQL Database schema (production)
        # Note: Uses Azure SQL-specific syntax for table creation
        
        # Create calls table if it doesn't exist
        c.execute('''
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='calls' AND xtype='U')
            CREATE TABLE calls (
                id INT IDENTITY(1,1) PRIMARY KEY,
                caller_id NVARCHAR(50),
                start_time NVARCHAR(50),
                end_time NVARCHAR(50),
                final_decision NVARCHAR(50)
            )
        ''')
        
        # Create conversation table if it doesn't exist
        c.execute('''
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='conversation' AND xtype='U')
            CREATE TABLE conversation (
                id INT IDENTITY(1,1) PRIMARY KEY,
                call_id INT,
                turn_index INT,
                speaker NVARCHAR(20),
                text NVARCHAR(MAX),
                timestamp NVARCHAR(50),
                FOREIGN KEY(call_id) REFERENCES calls(id)
            )
        ''')
    else:
        # SQLite schema (development)
        # Note: Uses SQLite-specific syntax for table creation
        
        # Create calls table if it doesn't exist
        c.execute('''
            CREATE TABLE IF NOT EXISTS calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                caller_id TEXT,
                start_time TEXT,
                end_time TEXT,
                final_decision TEXT
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
    
    if USE_AZURE_SQL and AZURE_SQL_CONNECTION_STRING:
        # Azure SQL: Insert and get the generated ID
        c.execute('INSERT INTO calls (caller_id, start_time) VALUES (?, ?)', (caller_id, start_time))
        c.execute('SELECT SCOPE_IDENTITY()')
    else:
        # SQLite: Insert and get the last inserted row ID
        c.execute('INSERT INTO calls (caller_id, start_time) VALUES (?, ?)', (caller_id, start_time))
        c.execute('SELECT last_insert_rowid()')
    
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

def log_final_decision(call_id, final_decision):
    """
    Log the final decision and end time for a call
    
    This function updates the call record with the final outcome and end time.
    It's called when a call is completed, transferred, or ended.
    
    Args:
        call_id: The database ID of the call to update
        final_decision: The final outcome (e.g., 'transferred', 'completed', 'ended_no_speech')
        
    Note: The end_time is automatically set to the current UTC time.
    """
    conn = get_connection()
    c = conn.cursor()
    
    # Record the call end time and final decision
    end_time = datetime.utcnow().isoformat()
    c.execute('UPDATE calls SET final_decision=?, end_time=? WHERE id=?', (final_decision, end_time, call_id))
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