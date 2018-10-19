# Created by DethMetalDuck
# Token_Handler deals with the generation and verification of tokens for the bot

import random
import hashlib
import Database_Handler
import Misc_Functionality
import re


# Function that sanitises function input
def sanitise_input(to_sanitise):
    # Token should only contain hex characters, i.e. a-f, 0-9. Anything else needs to be replaced with a 0
    # Loop through the input, checking if the current char is valid. If not then replace with a 0
    return re.sub("[^a-z0-9]", "0", to_sanitise)

# Function that generates a 12 character authentication token, then hashes it and returns that hash
def generate_authentication_token(user_id):
    # Create the string var we are going to have hold the 12 char token
    auth_token = ''

    # Create the array that will hold the generated characters
    character_array = []

    # String of possible characters
    possible_characters = 'aAbBcCdDeEfFgGhHiIjJkKlLmMnNoOpPqQrRsStTuUvVwWxXyYzZ1234567890!?*()'

    # Fill the character array with 12 characters
    for x in range(12):
        # Get random character from possible_characters
        char = possible_characters[random.randint(0, len(possible_characters) - 1)]

        # Put character in array
        character_array.append(char)

    # Randomly take from array until array is empty to create authentication token
    while len(character_array) != 0:
        # Add char to auth_token from a random place in character_array
        position_to_take_from = random.randint(0, len(character_array) - 1)
        auth_token += character_array[position_to_take_from]

        # Remove taken character from array
        character_array.pop(position_to_take_from)

    # Hash the auth_token then return it
    return hashlib.sha3_512(str(auth_token + user_id).encode('utf-8')).hexdigest()


# Function that takes a token and then returns the requestid for that token. Should only be called when token is valid
def get_request_id(token):
    # Send a query to the database to get the request id
    sql = 'SELECT RequestID FROM Tokens WHERE Token = \"%s\"' % token
    result = Database_Handler.send_select_query(sql)

    # Should only return 1 so this should be fine for now
    request_id = 0
    for x in result:
        request_id = x[0]

    return request_id


# Function that takes a given token and checks if it is valid and from the person who asked for it
def validate_token(token, user_id):
    # Send a query to the database asking if the token exists
    sql = 'SELECT * FROM Tokens WHERE Token = \"%s\" AND DATE_ADD(TokenCreationDateTime, INTERVAL 20 MINUTE) >= NOW()' % token
    results = Database_Handler.send_select_query(sql)

    # If there is 1 result return true
    if Misc_Functionality.count_results(results) == 1:
        # Token exists in database and isn't out of date, get the request's userid
        request_id = get_request_id(token)

        # Use the request id to go get the corresponding request
        sql = 'SELECT * FROM Requests WHERE RequestID = %d' % request_id
        request = Database_Handler.send_select_query(sql)

        # Request will contain (RequestID, MessageID, Username, UserID, CreationDate, EmailID)
        # UserID from request will be in string, convert given user_id to string to compare
        if str(user_id) == (request[0])[3]:
            return True
        else:
            return False
    else:
        return False


# Function that when called deletes expired tokens from the database
def delete_expired_tokens():
    # Set up the query
    sql = 'DELETE FROM Tokens WHERE DATE_ADD(TokenCreationDateTime, INTERVAL 30 MINUTE) < NOW()'

    # Send delete query to database handler
    Database_Handler.send_delete_query(sql)

    return
