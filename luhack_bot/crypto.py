from cryptography.fernet import Fernet

from luhack_bot.secrets import email_encryption_key

fernet = Fernet(email_encryption_key)
