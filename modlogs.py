import mysql.connector
from mysql.connector import Error
from datetime import datetime
import os

_connection = None

def create_connection():
    """Creates or retrieves a global connection to the mod_logs database."""
    global _connection
    try:
        if _connection is None or not _connection.is_connected():
            _connection = mysql.connector.connect(
                host=os.getenv('MOD_HOST'),
                port=os.getenv('MOD_PORT'),
                user=os.getenv('MOD_USER'),
                password=os.getenv('MOD_PASSWORD'),
                database=os.getenv('MOD_DATABASE')
            )
        return _connection
    except Error as e:
        print("Error connecting to mod_logs database:", e)
        return None

def create_logs_table():
    """Creates the 'mod_logs' table if it does not already exist."""
    connection = create_connection()
    if connection is None:
        return
    try:
        cursor = connection.cursor()
        create_table_query = """
        CREATE TABLE IF NOT EXISTS mod_logs (
            log_id INT AUTO_INCREMENT PRIMARY KEY,
            user_id VARCHAR(100),
            action_type VARCHAR(50),
            reason TEXT,
            moderator_id VARCHAR(100),
            timestamp DATETIME
        );
        """
        cursor.execute(create_table_query)
        connection.commit()
    except Error as e:
        print("Error creating mod_logs table:", e)
    finally:
        cursor.close()

def insert_mod_log(user_id, action_type, reason, moderator_id):
    """Inserts a new log entry into the 'mod_logs' table."""
    connection = create_connection()
    if connection is None:
        return
    try:
        cursor = connection.cursor()
        insert_query = """
        INSERT INTO mod_logs (user_id, action_type, reason, moderator_id, timestamp)
        VALUES (%s, %s, %s, %s, %s);
        """

        cursor.execute(insert_query, (user_id, action_type, reason, moderator_id, datetime.now()))
        connection.commit()
    except Error as e:
        print("Error inserting mod log:", e)
    finally:
        cursor.close()

# Example Test Function
def test_insert_mod_log():
    """Test the insert_mod_log function."""
    try:
        insert_mod_log("user123", "ban", "Inappropriate behavior", "mod456")
        print("insert_mod_log: SUCCESS")
    except Exception as e:
        print("insert_mod_log: FAIL", e)

if __name__ == "__main__":
    print("Testing insert_mod_log function...")
    test_insert_mod_log()
