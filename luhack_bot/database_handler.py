# Created by DethMetalDuck
# Database_Handler handles all database functionality required for the bot

import mysql.connector

from luhack_bot.secrets import (
    database_username,
    database_password,
    database_host,
    database,
    database_port,
)

# Config for mysql
config = {
    "user": database_username,
    "password": database_password,
    "host": database_host,
    "database": database,
    "raise_on_warnings": True,
    "port": database_port,
}


# Function that returns a connection to database
def start_database_connection():
    # Return the database connection
    return mysql.connector.connect(**config)


# Function that executes select queries and then returns the returned data
def send_select_query(query, params=None):
    # Set up connection
    connection = start_database_connection()

    # Set cursor
    db_cursor = connection.cursor()

    # Execute query
    db_cursor.execute(query, params)

    # Get results
    results = db_cursor.fetchall()

    # Close cursor and connection
    db_cursor.close()
    connection.close()

    # Return results
    return results


# Function that executes delete queries and then returns
def send_delete_query(query, params=None):
    # Set up connection
    connection = start_database_connection()

    # Set cursor
    db_cursor = connection.cursor()

    # Execute query
    db_cursor.execute(query, params)

    # Commit
    connection.commit()

    # Close cursor and connection
    db_cursor.close()
    connection.close()

    # Don't need last row id so just return
    return


# Function used for inserting into emails table, assumes that it receives the email already encrypted
def insert_into_emails(encrypted_email):
    # Set up the connection
    connection = start_database_connection()

    # Set cursor
    db_cursor = connection.cursor()

    # Set up sql statement
    sql = "INSERT INTO Emails (Email) VALUES (%s)"
    params = (encrypted_email,)

    # Execute statement
    db_cursor.execute(sql, params)

    # Commit
    connection.commit()

    # Get last row id for returning
    last_row_id = db_cursor.lastrowid

    # Close cursor and connection
    db_cursor.close()
    connection.close()

    # Return the insert ID for use later
    return last_row_id


# Function used for inserting into Requests table. Receives an array of values
def insert_into_requests(message_id, username, user_id, email_id):
    # Set up the connection
    connection = start_database_connection()

    # Set cursor
    db_cursor = connection.cursor()

    # Set up sql statement
    sql = "INSERT INTO Requests (MessageID, Username, UserID, EmailID) VALUES (%s, %s, %s, %s)"
    params = (message_id, username, user_id, email_id)

    # Execute statement
    db_cursor.execute(sql, params)

    # Commit
    connection.commit()

    # Get last row id for returning
    last_row_id = db_cursor.lastrowid

    # Close cursor and connection
    db_cursor.close()
    connection.close()

    # Return the insert ID for use later
    return last_row_id


# Function used for inserting into Tokens table. Receives an array of values
def insert_into_tokens(auth_token, request_insert_id):
    # Set up the connection
    connection = start_database_connection()

    # Set cursor
    db_cursor = connection.cursor()

    # Set up sql statement
    sql = "INSERT INTO Tokens (Token, RequestID) VALUES (%s, %s)"
    params = (auth_token, request_insert_id)

    # Execute statement
    db_cursor.execute(sql, params)

    # Commit
    connection.commit()

    # Close cursor and connection
    db_cursor.close()
    connection.close()

    # Don't need last row id so just return
    return


# Function used for inserting into Verified Users table. Recieves an array of values
def insert_into_verified_users(user_id, username, email_id):
    # Set up the connection
    connection = start_database_connection()

    # Set cursor
    db_cursor = connection.cursor()

    # Set up sql statement
    sql = "INSERT INTO VerifiedUsers (UserID, Username, EmailID) VALUES (%s, %s, %s)"
    params = (user_id, username, email_id)

    # Execute statement
    db_cursor.execute(sql, params)

    # Commit
    connection.commit()

    # Close cursor and connection
    db_cursor.close()
    connection.close()

    # Don't need last row id so just return
    return


# Function that takes a user id and checks if that user is already verified
def check_is_verified(user_id):
    # Query the verified users tables for the given user_id
    sql = 'SELECT * FROM VerifiedUsers WHERE UserID = %s'
    params = (user_id,)

    # Send query
    result = send_select_query(sql, params)

    return len(result) > 0
