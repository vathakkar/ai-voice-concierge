import streamlit as st
import sqlite3
import os
import pyodbc
import bcrypt
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database connection
USE_AZURE_SQL = os.getenv('USE_AZURE_SQL', 'false').lower() == 'true'

if USE_AZURE_SQL:
    def get_conn():
        return pyodbc.connect(os.getenv('AZURE_SQL_CONNECTION_STRING'))
else:
    def get_conn():
        return sqlite3.connect(os.getenv('SQLITE_DB_PATH', 'calls.db'))

def verify_admin(username, password):
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT password_hash FROM admin_credentials WHERE username = ?', (username,))
    row = c.fetchone()
    conn.close()
    if row:
        return bcrypt.checkpw(password.encode('utf-8'), row[0].encode('utf-8'))
    return False

def get_calls():
    conn = get_conn()
    c = conn.cursor()
    c.execute('''SELECT c.id, c.caller_id, c.start_time, c.final_decision, s.summary
                 FROM calls c LEFT JOIN call_summary s ON c.id = s.call_id
                 ORDER BY c.start_time DESC LIMIT 50''')
    rows = c.fetchall()
    conn.close()
    return rows

def get_exceptions():
    conn = get_conn()
    c = conn.cursor()
    c.execute('''SELECT phone_number, contact_name, category, added_date, is_active
                 FROM exception_phone_numbers ORDER BY contact_name ASC''')
    rows = c.fetchall()
    conn.close()
    return rows

def add_exception(phone, name, category):
    conn = get_conn()
    c = conn.cursor()
    if not phone.startswith('+'):
        phone = '+' + phone
    c.execute('SELECT id FROM exception_phone_numbers WHERE phone_number = ?', (phone,))
    if c.fetchone():
        st.warning(f"{phone} already exists.")
        conn.close()
        return
    added_date = datetime.utcnow().isoformat()
    c.execute('''INSERT INTO exception_phone_numbers (phone_number, contact_name, category, added_date, is_active)
                 VALUES (?, ?, ?, ?, 1)''', (phone, name, category, added_date))
    conn.commit()
    conn.close()
    st.success(f"Added {name} ({phone}) to exception list.")

def remove_exception(phone):
    conn = get_conn()
    c = conn.cursor()
    if not phone.startswith('+'):
        phone = '+' + phone
    c.execute('''UPDATE exception_phone_numbers SET is_active = 0 WHERE phone_number = ?''', (phone,))
    conn.commit()
    conn.close()
    st.success(f"Removed {phone} from exception list.")

def restore_exception(phone):
    conn = get_conn()
    c = conn.cursor()
    if not phone.startswith('+'):
        phone = '+' + phone
    c.execute('''UPDATE exception_phone_numbers SET is_active = 1 WHERE phone_number = ?''', (phone,))
    conn.commit()
    conn.close()
    st.success(f"Restored {phone} to exception list.")

# Streamlit UI
st.set_page_config(page_title="AI Concierge Dashboard", layout="wide")

if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False

if not st.session_state['authenticated']:
    st.title("AI Concierge Dashboard Login")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        if submitted:
            if verify_admin(username, password):
                st.session_state['authenticated'] = True
                st.success("Login successful!")
                st.experimental_rerun()
            else:
                st.error("Login failed. Please try again.")
    st.stop()

# Dashboard
st.title("AI Concierge Dashboard")
if st.button("Logout"):
    st.session_state['authenticated'] = False
    st.experimental_rerun()

st.header("Recent Calls")
calls = get_calls()
if calls:
    st.dataframe([
        {
            "Caller": c[1],
            "Time": c[2],
            "Outcome": c[3],
            "Summary": c[4] or ""
        } for c in calls
    ])
else:
    st.info("No calls found.")

st.header("Exception List Management")
exceptions = get_exceptions()
active_ex = [e for e in exceptions if e[4] == 1]
inactive_ex = [e for e in exceptions if e[4] == 0]

st.subheader("Active Exceptions")
for e in active_ex:
    col1, col2, col3, col4 = st.columns([3,3,2,2])
    col1.write(f"{e[1]} ({e[0]})")
    col2.write(e[2])
    col3.write(e[3][:10])
    if col4.button(f"Remove", key=f"remove_{e[0]}"):
        remove_exception(e[0])
        st.experimental_rerun()

st.subheader("Restore Exception")
for e in inactive_ex:
    col1, col2, col3, col4 = st.columns([3,3,2,2])
    col1.write(f"{e[1]} ({e[0]})")
    col2.write(e[2])
    col3.write(e[3][:10])
    if col4.button(f"Restore", key=f"restore_{e[0]}"):
        restore_exception(e[0])
        st.experimental_rerun()

st.subheader("Add New Exception")
with st.form("add_exception_form"):
    new_phone = st.text_input("Phone number (e.g., +1234567890)")
    new_name = st.text_input("Contact name")
    new_cat = st.text_input("Category (family/friends/work)", value="family")
    add_submitted = st.form_submit_button("Add")
    if add_submitted and new_phone and new_name:
        add_exception(new_phone, new_name, new_cat)
        st.experimental_rerun() 