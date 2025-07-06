#!/usr/bin/env python3
"""
Simple script to add phone numbers to the exception list directly in the database
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_db_connection():
    """Get database connection based on configuration"""
    USE_AZURE_SQL = os.getenv('USE_AZURE_SQL', 'false').lower() == 'true'
    
    if USE_AZURE_SQL:
        # Azure SQL Database
        import pyodbc
        connection_string = os.getenv('AZURE_SQL_CONNECTION_STRING')
        if not connection_string:
            print("❌ Error: AZURE_SQL_CONNECTION_STRING not found in environment variables")
            sys.exit(1)
        return pyodbc.connect(connection_string)
    else:
        # SQLite for local development
        import sqlite3
        db_path = os.getenv('SQLITE_DB_PATH', 'calls.db')
        conn = sqlite3.connect(db_path)
        
        # Create exception_phone_numbers table if it doesn't exist
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS exception_phone_numbers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone_number TEXT UNIQUE,
                contact_name TEXT,
                category TEXT,
                added_date TEXT,
                is_active INTEGER DEFAULT 1
            )
        ''')
        conn.commit()
        return conn

def add_exception_direct(phone_number, contact_name, category="family"):
    """Add exception phone number directly to database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Normalize phone number
    if not phone_number.startswith('+'):
        phone_number = '+' + phone_number
    
    # Check if already exists
    cursor.execute('SELECT id FROM exception_phone_numbers WHERE phone_number = ?', (phone_number,))
    if cursor.fetchone():
        print(f"⚠️  {contact_name} ({phone_number}) already exists in exception list")
        conn.close()
        return False
    
    # Add new exception
    added_date = datetime.utcnow().isoformat()
    cursor.execute('''
        INSERT INTO exception_phone_numbers (phone_number, contact_name, category, added_date, is_active)
        VALUES (?, ?, ?, ?, 1)
    ''', (phone_number, contact_name, category, added_date))
    
    conn.commit()
    conn.close()
    print(f"✅ Successfully added {contact_name} ({phone_number}) to exception list")
    return True

def list_exceptions_direct():
    """List all exception phone numbers directly from database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT phone_number, contact_name, category, added_date
        FROM exception_phone_numbers
        WHERE is_active = 1
        ORDER BY contact_name ASC
    ''')
    
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        print("📋 No exception phone numbers found")
        return
    
    print(f"📋 Current Exception List ({len(rows)} contacts):")
    print("-" * 60)
    
    for row in rows:
        print(f"📞 {row[1]} ({row[0]}) - {row[2]}")
        print(f"   Added: {row[3]}")
        print()

def check_exception_direct(phone_number):
    """Check if phone number is in exception list directly from database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Normalize phone number
    if not phone_number.startswith('+'):
        phone_number = '+' + phone_number
    
    cursor.execute('''
        SELECT contact_name, category, added_date
        FROM exception_phone_numbers
        WHERE phone_number = ? AND is_active = 1
    ''', (phone_number,))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        print(f"✅ {phone_number} is in exception list:")
        print(f"   Contact: {row[0]}")
        print(f"   Category: {row[1]}")
        print(f"   Added: {row[2]}")
    else:
        print(f"❌ {phone_number} is NOT in exception list")

def remove_exception_direct(phone_number):
    """Soft delete a phone number from the exception list (set is_active=0)"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Normalize phone number
    if not phone_number.startswith('+'):
        phone_number = '+' + phone_number

    cursor.execute('''
        UPDATE exception_phone_numbers
        SET is_active = 0
        WHERE phone_number = ? AND is_active = 1
    ''', (phone_number,))
    conn.commit()
    rows_affected = cursor.rowcount
    conn.close()

    if rows_affected > 0:
        print(f"✅ {phone_number} has been removed (soft deleted) from the exception list.")
    else:
        print(f"❌ {phone_number} was not found or is already inactive.")

def restore_exception_direct(phone_number):
    """Restore (reactivate) a soft-deleted phone number in the exception list (set is_active=1)"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Normalize phone number
    if not phone_number.startswith('+'):
        phone_number = '+' + phone_number

    cursor.execute('''
        UPDATE exception_phone_numbers
        SET is_active = 1
        WHERE phone_number = ? AND is_active = 0
    ''', (phone_number,))
    conn.commit()
    rows_affected = cursor.rowcount
    conn.close()

    if rows_affected > 0:
        print(f"✅ {phone_number} has been restored (reactivated) in the exception list.")
    else:
        print(f"❌ {phone_number} was not found or is already active.")

def main():
    """Main function"""
    print("🤖 AI Voice Concierge - Direct Database Exception Manager")
    print("=" * 60)
    
    # Check database connection
    try:
        conn = get_db_connection()
        conn.close()
        print("✅ Database connection successful")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return
    
    # Command line remove mode
    if len(sys.argv) == 3 and sys.argv[1] == "remove":
        phone = sys.argv[2]
        remove_exception_direct(phone)
        return
    # Command line restore mode
    if len(sys.argv) == 3 and sys.argv[1] == "restore":
        phone = sys.argv[2]
        restore_exception_direct(phone)
        return
    
    if len(sys.argv) >= 3:
        # Command line add mode
        phone = sys.argv[1]
        name = sys.argv[2]
        category = sys.argv[3] if len(sys.argv) > 3 else "family"
        add_exception_direct(phone, name, category)
    else:
        # Interactive mode
        while True:
            print("\nOptions:")
            print("1. Add new exception contact")
            print("2. List all exceptions")
            print("3. Check if number is in exceptions")
            print("4. Remove a number from exceptions")
            print("5. Restore a number to exceptions")
            print("6. Exit")
            
            choice = input("\nEnter your choice (1-6): ").strip()
            
            if choice == "1":
                print("\n--- Add New Exception Contact ---")
                phone = input("Phone number (e.g., +1234567890): ").strip()
                name = input("Contact name (e.g., Mom): ").strip()
                category = input("Category (family/friends/work) [default: family]: ").strip() or "family"
                
                if phone and name:
                    add_exception_direct(phone, name, category)
                else:
                    print("❌ Phone number and contact name are required")
                    
            elif choice == "2":
                print("\n--- Current Exception List ---")
                list_exceptions_direct()
                
            elif choice == "3":
                print("\n--- Check Exception Status ---")
                phone = input("Phone number to check (e.g., +1234567890): ").strip()
                if phone:
                    check_exception_direct(phone)
                else:
                    print("❌ Phone number is required")
                    
            elif choice == "4":
                print("\n--- Remove Exception Contact ---")
                phone = input("Phone number to remove (e.g., +1234567890): ").strip()
                if phone:
                    remove_exception_direct(phone)
                else:
                    print("❌ Phone number is required")
            elif choice == "5":
                print("\n--- Restore Exception Contact ---")
                phone = input("Phone number to restore (e.g., +1234567890): ").strip()
                if phone:
                    restore_exception_direct(phone)
                else:
                    print("❌ Phone number is required")
            elif choice == "6":
                print("👋 Goodbye!")
                break
            else:
                print("❌ Invalid choice. Please enter 1-6.")

if __name__ == "__main__":
    main() 