import sqlite3
import pandas as pd
from datetime import datetime
import hashlib # <-- NEW: Built-in library for password encryption

DB_FILE = "pdf_history.db"

# ==========================================
# SECURITY LOGIC
# ==========================================
def hash_password(password):
    """Encrypts the password into a secure, unreadable string."""
    return hashlib.sha256(password.encode()).hexdigest()

# ==========================================
# DATABASE INITIALIZATION
# ==========================================
def init_db():
    """Creates the tables if they do not exist."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # 1. The original PDF tracking table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS uploads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            filepath TEXT,
            upload_date TEXT
        )
    ''')
    
    # 2. NEW: The User Accounts table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password_hash TEXT,
            role TEXT
        )
    ''')
    
    # 3. NEW: Auto-create the Master Admin if the table is empty
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            ("admin", hash_password("RPA2026!"), "admin") # Your default login
        )
        
    conn.commit()
    conn.close()

# ==========================================
# USER MANAGEMENT LOGIC
# ==========================================
def verify_user(username, password):
    """Checks if the username exists and the password matches the hash."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT password_hash, role FROM users WHERE username = ?", (username,))
    result = cursor.fetchone()
    conn.close()

    if result:
        stored_hash, role = result
        # Compare the entered password against the saved encrypted version
        if stored_hash == hash_password(password):
            return True, role
            
    return False, None

def create_user(username, password, role="user"):
    """Creates a new user in the database."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (username, hash_password(password), role)
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        # This triggers if the username already exists (because of TEXT UNIQUE in table setup)
        return False 

def get_all_users():
    """Returns a list of all users for the Admin panel."""
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT id, username, role FROM users", conn)
    conn.close()
    return df

# ==========================================
# PDF TRACKING LOGIC (Unchanged)
# ==========================================
def log_upload(filename, filepath):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "INSERT INTO uploads (filename, filepath, upload_date) VALUES (?, ?, ?)", 
        (filename, filepath, current_time)
    )
    conn.commit()
    conn.close()

def get_upload_history():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM uploads ORDER BY upload_date DESC", conn)
    conn.close()
    return df