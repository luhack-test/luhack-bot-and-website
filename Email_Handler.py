# Created by DethMetalDuck
# Email Handler deals with all the functionality required for emails. Interacts with Database_Handler to do so

import smtplib
import Database_Handler
from AES_Cipher import AESCipher

# Aes cipher key
aes_key = '***REMOVED***'


# Stole most of the code and then modified it so not really commented
def send_email(email, token):
    gmail_user = '***REMOVED***'
    gmail_password = '***REMOVED***'

    sent_from = gmail_user
    to = email
    subject = 'LUHack Discord Verification Bot Authentication Email'
    body = 'Hello!\n' \
           'You are receiving this email because you have requested to authenticate yourself as a valid Lancaster University student on the LUHack Discord server.\n\n' \
           '' \
           '' \
           'Your authentication token is: %s' % token
    email_text = """\  
    From: %s  
    To: %s  
    Subject: %s

    %s
    """ % (sent_from, email, subject, body)

    try:
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.ehlo()
        server.login(gmail_user, gmail_password)
        server.sendmail(sent_from, to, email_text)
        server.close()

        print('Email Sent')
    except:
        print('Something went wrong...')


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
    # Check if the given email contains @lancaster.ac.uk
    if "@lancaster.ac.uk" in email:
        return True
    # Otherwise check if it contains live.lancs.ac.uk
    elif "live.lancs.ac.uk" in email:
        return True
    # Otherwise return false
    else:
        return False


# Function used to check if an email already exists in the system
def check_email_exists(email):
    # Encrypt email
    encrypted_email = encrypt_email(email)

    # Query database for email
    sql = 'SELECT * FROM Emails WHERE Email = %s', encrypted_email
    results = Database_Handler.send_select_query(sql)

    # Count how many results there are
    count = 0
    for x in results:
        count += 1

    # If count = 0, return false
    if count == 0:
        return False

    # Otherwise return true
    else:
        return True
