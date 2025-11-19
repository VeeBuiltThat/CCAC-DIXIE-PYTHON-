import mysql.connector
from mysql.connector import Error
import os

_connection = None

def create_connection():
    global _connection

   
    host = os.getenv('MOD_HOST', 'localhost')
    port = int(os.getenv('MOD_PORT', 3306))

    if _connection and _connection.is_connected():
        return _connection

    try:
        _connection = mysql.connector.connect(
            host=host,
            port=port,
            user=os.getenv('MOD_USER', 'root'),
            password=os.getenv('MOD_PASSWORD', ''),
            database=os.getenv('MOD_DATABASE', 'mod_logs')
        )
        print("✅ Database connection successful!")
        return _connection
    except Error as e:
        print("❌ Error connecting to verification database:", e)
        return None


def create_table():
    """Creates the 'user_data' table if it does not already exist."""
    connection = create_connection()
    if connection is None:
        return
    try:
        cursor = connection.cursor()
        create_table_query = """
            CREATE TABLE IF NOT EXISTS user_data (
                join_time DATETIME NOT NULL,
                user_id VARCHAR(100) PRIMARY KEY,
                password VARCHAR(100) NOT NULL
            );

        """
        cursor.execute(create_table_query)
        connection.commit()
    except Error as e:
        print("Error creating table:", e)
    finally:
        cursor.close()

def add_user(user_id, join_time, password):
    """Adds a new user record to the 'user_data' table."""
    connection = create_connection()
    if connection is None:
        return
    try:
        cursor = connection.cursor()
        insert_query = """
        INSERT INTO user_data (user_id, join_time, password)
        VALUES (%s, %s, %s);
        """
        cursor.execute(insert_query, (user_id, join_time, password))
        connection.commit()
    except Error as e:
        print("Error inserting new user:", e)
    finally:
        cursor.close()

def get_user_by_id(user_id):
    """Retrieves a user record based on user_id."""
    connection = create_connection()
    if connection is None:
        return None
    try:
        cursor = connection.cursor(dictionary=True)
        select_query = "SELECT * FROM user_data WHERE user_id = %s;"
        cursor.execute(select_query, (user_id,))
        result = cursor.fetchone()
        return result
    except Error as e:
        print("Error retrieving user:", e)
        return None
    finally:
        cursor.close()

def get_password_by_user_id(user_id):
    """Returns the password of a user based on user_id."""
    connection = create_connection()
    if connection is None:
        return None
    try:
        cursor = connection.cursor(dictionary=True)  
        select_query = "SELECT password FROM user_data WHERE user_id = %s;"
        cursor.execute(select_query, (user_id,))
        result = cursor.fetchone()
        return result['password'] if result else None  
    except Error as e:
        print("Error retrieving password:", e)
        return None
    finally:
        cursor.close()

def get_join_time_by_user_id(user_id):
    """Returns the join time of a user based on user_id."""
    connection = create_connection()
    if connection is None:
        return None
    try:
        cursor = connection.cursor(dictionary=True) 
        select_query = "SELECT join_time FROM user_data WHERE user_id = %s;"
        cursor.execute(select_query, (user_id,))
        result = cursor.fetchone()
        return result['join_time'] if result else None  
    except Error as e:
        print("Error retrieving join time:", e)
        return None
    finally:
        cursor.close()


def check_user_exists(user_id):
    connection = create_connection()
    if connection is None:
        print("No connection could be established.")
        return False

    try:
        cursor = connection.cursor()  
        cursor.execute("SELECT COUNT(*) FROM user_data WHERE user_id = %s", (user_id,))

        result = cursor.fetchone()

        cursor.close()

        if result and result[0] > 0:
            return True
        return False

    except Error as e:
        print(f"Error while checking user exists: {e}")
        return False
    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()

def delete_user_by_id(user_id):
    """Deletes a user from the user_data table based on user_id."""
    connection = create_connection()
    if connection is None:
        return False  
    try:
        cursor = connection.cursor()
        delete_query = "DELETE FROM user_data WHERE user_id = %s;"
        cursor.execute(delete_query, (user_id,))
        connection.commit() 
        print(f"User with ID {user_id} deleted successfully.")
        return cursor.rowcount > 0  
    except Error as e:
        print(f"Error deleting user with ID {user_id}: {e}")
        return False
    finally:
        cursor.close()


__all__ = [
    "create_connection",
    "create_table",
    "add_user",
    "get_user_by_id",
    "get_password_by_user_id",
    "get_join_time_by_user_id",
    "check_user_exists",
    "delete_user_by_id"
]