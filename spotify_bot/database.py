import sqlite3
import os
import contextlib

DB_NAME = "spotify_payments.db"

@contextlib.contextmanager
def get_connection():
    """Context manager that handles connection opening, headers, commit/rollback, and closing."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    with get_connection() as conn:
        c = conn.cursor()
        
        # Groups Table
        c.execute('''CREATE TABLE IF NOT EXISTS groups (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT UNIQUE NOT NULL,
                        monthly_cost REAL DEFAULT 56.0
                    )''')

        # Members Table
        # user_id is UNIQUE to enforce one family per user
        c.execute('''CREATE TABLE IF NOT EXISTS members (
                        user_id INTEGER PRIMARY KEY,
                        group_id INTEGER NOT NULL,
                        name TEXT NOT NULL,
                        balance REAL DEFAULT 0.0,
                        gcash_name TEXT UNIQUE,
                        FOREIGN KEY(group_id) REFERENCES groups(id)
                    )''')
        
        # Migrations: Add new columns if they don't exist
        try:
            c.execute("ALTER TABLE groups ADD COLUMN billing_day INTEGER DEFAULT 1")
        except sqlite3.OperationalError:
            pass # Column exists

        try:
            c.execute("ALTER TABLE groups ADD COLUMN last_billed_date TEXT")
        except sqlite3.OperationalError:
            pass # Column exists

        try:
            c.execute("ALTER TABLE groups ADD COLUMN channel_id INTEGER")
        except sqlite3.OperationalError:
            pass # Column exists

# --- Group Management ---
def create_group(name, channel_id=None):
    try:
        with get_connection() as conn:
            cur = conn.execute("INSERT INTO groups (name, channel_id) VALUES (?, ?)", (name, channel_id))
            return cur.lastrowid
    except sqlite3.IntegrityError:
        return None # Name exists

def delete_group_cascade(group_id):
    """Deletes a group and all its members."""
    with get_connection() as conn:
        conn.execute("DELETE FROM members WHERE group_id = ?", (group_id,))
        conn.execute("DELETE FROM groups WHERE id = ?", (group_id,))

def update_group_channel(group_id, channel_id):
    with get_connection() as conn:
        conn.execute("UPDATE groups SET channel_id = ? WHERE id = ?", (channel_id, group_id))

def get_group_by_name(name):
    with get_connection() as conn:
        cur = conn.execute("SELECT * FROM groups WHERE name = ?", (name,))
        return cur.fetchone()

def get_group_by_id(group_id):
    with get_connection() as conn:
        cur = conn.execute("SELECT * FROM groups WHERE id = ?", (group_id,))
        return cur.fetchone()

def get_all_groups():
    with get_connection() as conn:
        cur = conn.execute("SELECT * FROM groups")
        return cur.fetchall()

def set_billing_day(group_id, day):
    with get_connection() as conn:
        conn.execute("UPDATE groups SET billing_day = ? WHERE id = ?", (day, group_id))

def get_due_groups(current_day, current_month_str):
    """
    Returns groups that match the current_day and haven't been billed this month (current_month_str).
    current_month_str format: 'YYYY-MM'
    """
    with get_connection() as conn:
        # We check if billing_day matches, AND if last_billed_date is NOT starting with current_month_str
        # Note: simplistic check. If last_billed_date is NULL, we bill.
        # We fetch all candidates and filter in python or do a complex query. 
        # Query approach:
        query = """
            SELECT * FROM groups 
            WHERE billing_day = ? 
            AND (last_billed_date IS NULL OR last_billed_date != ?)
        """
        cur = conn.execute(query, (current_day, current_month_str))
        return cur.fetchall()

def update_last_billed_date(group_id, date_str):
    with get_connection() as conn:
        conn.execute("UPDATE groups SET last_billed_date = ? WHERE id = ?", (date_str, group_id))

# --- Member Management ---
def add_member(user_id, name, group_id):
    try:
        with get_connection() as conn:
            conn.execute("INSERT INTO members (user_id, group_id, name, balance) VALUES (?, ?, ?, 0.0)", (user_id, group_id, name))
            return True
    except sqlite3.IntegrityError:
        return False # Already in a group

def get_member(user_id):
    with get_connection() as conn:
        cur = conn.execute("SELECT m.*, g.name as group_name, g.monthly_cost, g.billing_day, g.last_billed_date FROM members m JOIN groups g ON m.group_id = g.id WHERE m.user_id = ?", (user_id,))
        return cur.fetchone()

def remove_member(user_id):
    with get_connection() as conn:
        conn.execute("DELETE FROM members WHERE user_id = ?", (user_id,))

def get_members_in_group(group_id):
    with get_connection() as conn:
        cur = conn.execute("SELECT * FROM members WHERE group_id = ?", (group_id,))
        return cur.fetchall()

# --- Finance ---
def add_funds(user_id, amount):
    with get_connection() as conn:
        conn.execute("UPDATE members SET balance = balance + ? WHERE user_id = ?", (amount, user_id))

def set_group_cost(group_id, amount):
    with get_connection() as conn:
        conn.execute("UPDATE groups SET monthly_cost = ? WHERE id = ?", (amount, group_id))

def process_month_for_group(group_id):
    group = get_group_by_id(group_id)
    if not group: return 0
    cost = group['monthly_cost']
    with get_connection() as conn:
        conn.execute("UPDATE members SET balance = balance - ? WHERE group_id = ?", (cost, group_id))
    return cost

# --- GCash / Email Integration ---
def link_gcash_name(user_id, gcash_name):
    try:
        with get_connection() as conn:
            conn.execute("UPDATE members SET gcash_name = ? WHERE user_id = ?", (gcash_name, user_id))
            return True
    except sqlite3.IntegrityError:
        return False # Name taken

def get_member_by_gcash_name(gcash_name):
    with get_connection() as conn:
        # Case insensitive search
        cur = conn.execute("SELECT * FROM members WHERE lower(gcash_name) = lower(?)", (gcash_name,))
        return cur.fetchone()
