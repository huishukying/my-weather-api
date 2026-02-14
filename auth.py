
import hashlib
import os
import base64

def hash_password(password: str) -> str:
    salt = os.urandom(32)
    key = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt,
        100000 
    )
    return base64.b64encode(salt + key).decode('ascii')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        decoded = base64.b64decode(hashed_password)
        salt = decoded[:32]
        stored_key = decoded[32:]
        
        key = hashlib.pbkdf2_hmac(
            'sha256',
            plain_password.encode('utf-8'),
            salt,
            100000
        )
        return key == stored_key
    except:
        return False
