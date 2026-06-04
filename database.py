import sqlite3
import pandas as pd
from datetime import datetime
import hashlib

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
    
    # 2. The User Accounts table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password_hash TEXT,
            role TEXT
        )
    ''')
    
    # 3. Auto-create the Master Admins
    # Using 'INSERT OR IGNORE' prevents errors if these users already exist in the database.
    
    # Fixed User 1 (Original)
    cursor.execute(
        "INSERT OR IGNORE INTO users (username, password_hash, role) VALUES (?, ?, ?)",
        ("admin", hash_password("RPA2026!"), "admin") 
    )
    
    # Fixed User 2 (New)
    cursor.execute(
        "INSERT OR IGNORE INTO users (username, password_hash, role) VALUES (?, ?, ?)",
        ("admin2", hash_password("@newadmin123"), "admin") 
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
        return False 

def get_all_users():
    """Returns a list of all users for the Admin panel."""
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT id, username, role FROM users", conn)
    conn.close()
    return df

# ==========================================
# PDF TRACKING LOGIC
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

def delete_upload_log(filename):
    """Deletes a file record from the database."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Uses the correct table name 'uploads' and LIKE to ensure a match
        cursor.execute("DELETE FROM uploads WHERE filename LIKE ?", ('%' + filename + '%',))
        
        rows_erased = cursor.rowcount 
        conn.commit()
        conn.close()
        
        return rows_erased > 0
    except Exception as e:
        print(f"Database delete error: {e}")
        return False
    
    
def delete_user(username):
    """Deletes a user from the database. Prevents deleting the master admin."""
    # Safety lock: Never allow the default admin to be deleted!
    if username.lower() == "admin":
        return False 
        
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE username = ?", (username,))
        rows_erased = cursor.rowcount 
        conn.commit()
        conn.close()
        return rows_erased > 0
    except Exception as e:
        print(f"Database user delete error: {e}")
        return False

def reset_user_password(username, new_password):
    """Updates the password for an existing user."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET password_hash = ? WHERE username = ?",
            (hash_password(new_password), username)
        )
        rows_updated = cursor.rowcount
        conn.commit()
        conn.close()
        return rows_updated > 0
    except Exception as e:
        print(f"Database password update error: {e}")
        return False