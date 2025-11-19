import discord
from discord.ext import commands
from datetime import timedelta
import mysql.connector
from mysql.connector import Error   
from discord.utils import utcnow
import os

_connection = None
_connection_status_printed = False

def create_connection():
    global _connection, _connection_status_printed

    if _connection and _connection.is_connected():
        if not _connection_status_printed:
            print("✅ Database connection successful!")
            _connection_status_printed = True
        return _connection

    try:
        _connection = mysql.connector.connect(
            host=os.getenv('MOD_HOST', 'localhost'),
            port=int(os.getenv('MOD_PORT', 3306)),
            user=os.getenv('MOD_USER', 'root'),
            password=os.getenv('MOD_PASSWORD', ''),
            database=os.getenv('MOD_DATABASE', 'mod_logs')
        )
        print("✅ Database connection successful!")
        _connection_status_printed = True
        return _connection
    except Error as e:
        print("❌ Error connecting to database:", e)
        _connection_status_printed = True
        return None


def create_mod_log_table():
    """Ensures the mod_logs table exists with the necessary columns."""
    connection = create_connection()
    if connection is None:
        return
    try:
        cursor = connection.cursor()
        create_table_query = """
        CREATE TABLE IF NOT EXISTS mod_logs (
            log_id INT AUTO_INCREMENT PRIMARY KEY,
            user_id VARCHAR(100) NOT NULL,
            reason TEXT NOT NULL,
            moderator_id VARCHAR(100) NOT NULL,
            action_type VARCHAR(100) NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            notes TEXT DEFAULT NULL  -- Added Notes column
        );
        """
        cursor.execute(create_table_query)
        connection.commit()
        print("Mod log table is ready or already exists.")
    except Error as e:
        print("Error creating mod_logs table:", e)
    finally:
        cursor.close()
        
def get_notes(user_id):
    """Retrieves notes for a specific user."""
    connection = create_connection()
    if connection is None:
        return None
    try:
        cursor = connection.cursor(dictionary=True, buffered=True)
        select_query = """
        SELECT notes FROM mod_logs WHERE user_id = %s;
        """
        cursor.execute(select_query, (user_id,))
        result = cursor.fetchone()
        return result['notes'] if result else None
    except Error as e:
        print(f"Error retrieving notes: {e}")
        return None
    finally:
        cursor.close()

def add_note_to_db(user_id: int, note: str):
    """Adds a note to a user in the mod_logs table."""
    connection = create_connection()
    if connection is None:
        return False
    try:
        cursor = connection.cursor()
        update_query = """
        UPDATE mod_logs SET notes = CONCAT(COALESCE(notes, ''), %s) WHERE user_id = %s;
        """
        cursor.execute(update_query, (f'\n{note}', user_id))
        connection.commit()
        print(f"Note added for user {user_id}.")
        return True
    except Error as e:
        print(f"Error adding note: {e}")
        return False
    finally:
        cursor.close()
        
def add_mod_log(user_id, reason, moderator_id, action_type):
    """Adds a new moderation log to the 'mod_logs' table."""
    connection = create_connection()
    if connection is None:
        print("No connection to database. Cannot insert log.")
        return False
    try:
        cursor = connection.cursor()
        timestamp = utcnow().strftime('%Y-%m-%d %H:%M:%S') 
        insert_query = """
        INSERT INTO mod_logs (user_id, reason, moderator_id, action_type, timestamp)
        VALUES (%s, %s, %s, %s, %s);
        """
        cursor.execute(insert_query, (user_id, reason, moderator_id, action_type, timestamp))
        connection.commit()
        print(f"Log added for user {user_id} with action_type {action_type}.")
        return True
    except Error as e:
        print(f"Error inserting moderation log: {e}")
        return False
    finally:
        cursor.close()



def add_action_column():
    """Adds the 'action_type' column to the 'mod_logs' table if it doesn't exist."""
    connection = create_connection()
    if connection is None:
        return
    try:
        cursor = connection.cursor()

        alter_table_query = """
        ALTER TABLE mod_logs
        ADD COLUMN action_type VARCHAR(100) NOT NULL DEFAULT 'unknown';
        """
        cursor.execute(alter_table_query)
        connection.commit()
    except Error as e:
        print("Error adding 'action_type' column:", e)
    finally:
        cursor.close()
        connection.close()




def get_mod_logs_by_user(user_id):
    """Retrieves all moderation logs for a specific user."""
    connection = create_connection()
    if connection is None:
        return None
    try:
        cursor = connection.cursor(dictionary=True, buffered=True)
        select_query = "SELECT * FROM mod_logs WHERE user_id = %s ORDER BY timestamp DESC;"
        cursor.execute(select_query, (user_id,))
        result = cursor.fetchall()
        return result
    except Error as e:
        print("Error retrieving mod logs:", e)
        return None
    finally:
        cursor.close()
        connection.close()

def get_mod_logs_by_moderator(moderator_id):
    """Retrieves all moderation logs issued by a specific moderator."""
    connection = create_connection()
    if connection is None:
        return None
    try:
        cursor = connection.cursor(dictionary=True, buffered=True)
        select_query = "SELECT * FROM mod_logs WHERE moderator_id = %s ORDER BY timestamp DESC;"
        cursor.execute(select_query, (moderator_id,))
        result = cursor.fetchall()
        return result
    except Error as e:
        print("Error retrieving logs by moderator:", e)
        return None
    finally:
        cursor.close()
        connection.close()

def check_log_exists(log_id):
    """Checks if a specific moderation log exists based on log_id."""
    connection = create_connection()
    if connection is None:
        return False
    try:
        cursor = connection.cursor()
        select_query = "SELECT 1 FROM mod_logs WHERE log_id = %s;"
        cursor.execute(select_query, (log_id,))
        result = cursor.fetchone()
        return bool(result)
    except Error as e:
        print("Error checking if log exists:", e)
        return False
    finally:
        cursor.close()
        connection.close()

def delete_mod_log_by_id(log_id):
    """Deletes a moderation log from the database based on log_id."""
    connection = create_connection()
    if connection is None:
        return False
    try:
        cursor = connection.cursor()
        delete_query = "DELETE FROM mod_logs WHERE log_id = %s;"
        cursor.execute(delete_query, (log_id,))
        connection.commit()
        print(f"Log with ID {log_id} deleted successfully.")
        return cursor.rowcount > 0
    except Error as e:
        print(f"Error deleting log with ID {log_id}: {e}")
        return False
    finally:
        cursor.close()
        connection.close()
        
def get_warnings(user_id):
    """Fetches minor and major warnings for a user from DB."""
    connection = create_connection()
    if connection is None:
        return [], []
    
    try:
        cursor = connection.cursor(dictionary=True, buffered=True)  # <-- add buffered=True
        query = """
        SELECT log_id, action_type, reason, moderator_id AS mod_id, timestamp AS date 
        FROM mod_logs 
        WHERE user_id = %s;
        """
        cursor.execute(query, (user_id,))
        logs = cursor.fetchall()
        
        minor_warnings = [log for log in logs if log["action_type"].lower() == "minor_warning"]
        major_warnings = [log for log in logs if log["action_type"].lower() == "major_warning"]

        return minor_warnings, major_warnings
    except Error as e:
        print(f"Error retrieving warnings: {e}")
        return [], []
    finally:
        cursor.close()
        connection.close()

        
def remove_warning(user_id, action_type, log_id):
    """Removes a warning from the database by log ID."""
    connection = create_connection()
    if connection is None:
        return False
    try:
        cursor = connection.cursor()
        # Ensure correct action_type format
        action_type = f"{action_type}_warning"  
        delete_query = """
        DELETE FROM mod_logs 
        WHERE user_id = %s AND action_type = %s AND log_id = %s
        LIMIT 1;
        """
        cursor.execute(delete_query, (user_id, action_type, log_id))
        connection.commit()
        return cursor.rowcount > 0 
    except Error as e:
        print(f"Error removing warning: {e}")
        return False
    finally:
        cursor.close()
        connection.close()

        

__all__ = [
    "create_connection",
    "create_mod_log_table",
    "add_mod_log",
    "get_mod_logs_by_user",
    "get_mod_logs_by_moderator",
    "check_log_exists",
    "delete_mod_log_by_id",
    "get_warnings",
    "create_connection",
    "get_notes",
    "action_type",
    "add_note_to_db"
]
