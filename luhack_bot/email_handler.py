# Created by DethMetalDuck
# Email Handler deals with all the functionality required for emails. Interacts with database_handler to do so
import textwrap

import smtplib
from luhack_bot import database_handler
from luhack_bot.aes_cipher import AESCipher
from luhack_bot.secrets import aes_encryption_key, email_username, email_password

# Aes cipher key
aes_key = aes_encryption_key


# Stole most of the code and then modified it so not really commented
def send_email(email, token):
    gmail_user = email_username
    gmail_password = email_password

    sent_from = gmail_user
    to = email
    subject = "LUHack Discord Verification Bot Authentication Email"

    body = textwrap.dedent(
        f"""
        Hello!
        You are receiving this email because you have requested to authenticate yourself as a valid Lancaster University student on the LUHack Discord server.


        Your authentication token is: {token}
        """
    )

    email_text = textwrap.dedent(
        f"""
        From: {sent_from}
        To: {email}
        Subject: {subject}

        {body}
        """
    )

    try:
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.ehlo()
        server.login(gmail_user, gmail_password)
        server.sendmail(sent_from, to, email_text)
        server.close()

        print("Email Sent")
    except smtplib.SMTPException:
        print("Something went wrong...")


# Function used to encrypt the given email
def encrypt_email(email):
    # Make the aes cipher with key
    cipher = AESCipher(key=aes_key)

    # Encrypt the given email
    encrypted = cipher.encrypt(email)

    # Return encrypted email
    return encrypted


# Function used to decrypt a given encrypted email
def decrypt_email(encrypted_email):
    # Make the aes cipher with the key
    cipher = AESCipher(key=aes_key)

    # Decrypt the given encrypted email
    decrypted = cipher.decrypt(encrypted_email)

    # Return decrypted email
    return decrypted


# Function that checks if it is a lancs email
def check_lancs_email(email):
    return "@lancaster.ac.uk" in email or "live.lancs.ac.uk" in email


# Function used to check if an email already exists in the system
def check_email_exists(email):
    # Encrypt email
    encrypted_email = encrypt_email(email)

    # Query database for email
    sql = "SELECT * FROM Emails WHERE Email = %s"
    params = (encrypted_email,)
    results = database_handler.send_select_query(sql, params)

    return len(results) > 0
