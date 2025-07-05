import os
import sqlite3
from datetime import datetime
from config import SQLITE_DB_PATH, AZURE_SQL_CONNECTION_STRING

# Database configuration
USE_AZURE_SQL = os.getenv('USE_AZURE_SQL', 'false').lower() == 'true'

def get_connection():
    """Get database connection based on configuration"""
    if USE_AZURE_SQL and AZURE_SQL_CONNECTION_STRING:
        try:
            import pyodbc
            return pyodbc.connect(AZURE_SQL_CONNECTION_STRING)
        except ImportError:
            print("Warning: pyodbc not installed, falling back to SQLite")
            return sqlite3.connect(SQLITE_DB_PATH)
    else:
        return sqlite3.connect(SQLITE_DB_PATH)

# Initialize the database and create tables if they don't exist
def init_db():
    conn = get_connection()
    c = conn.cursor()
    
    if USE_AZURE_SQL and AZURE_SQL_CONNECTION_STRING:
        # Azure SQL Database schema
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
        # SQLite schema
        c.execute('''
            CREATE TABLE IF NOT EXISTS calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                caller_id TEXT,
                start_time TEXT,
                end_time TEXT,
                final_decision TEXT
            )
        ''')
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
    
    conn.commit()
    conn.close()

# Log a new call and return its ID
def log_new_call(caller_id):
    conn = get_connection()
    c = conn.cursor()
    start_time = datetime.utcnow().isoformat()
    
    if USE_AZURE_SQL and AZURE_SQL_CONNECTION_STRING:
        c.execute('INSERT INTO calls (caller_id, start_time) VALUES (?, ?)', (caller_id, start_time))
        c.execute('SELECT SCOPE_IDENTITY()')
    else:
        c.execute('INSERT INTO calls (caller_id, start_time) VALUES (?, ?)', (caller_id, start_time))
        c.execute('SELECT last_insert_rowid()')
    
    call_id = c.fetchone()[0]
    conn.commit()
    conn.close()
    return int(call_id)

# Log a conversation turn
def log_conversation_turn(call_id, turn_index, speaker, text):
    conn = get_connection()
    c = conn.cursor()
    timestamp = datetime.utcnow().isoformat()
    c.execute('INSERT INTO conversation (call_id, turn_index, speaker, text, timestamp) VALUES (?, ?, ?, ?, ?)',
              (call_id, turn_index, speaker, text, timestamp))
    conn.commit()
    conn.close()

# Log the final decision and end time for a call
def log_final_decision(call_id, final_decision):
    conn = get_connection()
    c = conn.cursor()
    end_time = datetime.utcnow().isoformat()
    c.execute('UPDATE calls SET final_decision=?, end_time=? WHERE id=?', (final_decision, end_time, call_id))
    conn.commit()
    conn.close()

# Get recent conversations
def get_recent_conversations(limit=10):
    conn = get_connection()
    c = conn.cursor()
    
    # Get recent calls with conversation details
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
    
    # Group by call
    conversations = {}
    for row in rows:
        call_id = row[0]
        if call_id not in conversations:
            conversations[call_id] = {
                "call_id": call_id,
                "caller_id": row[1],
                "start_time": row[2],
                "end_time": row[3],
                "final_decision": row[4],
                "conversation": []
            }
        
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