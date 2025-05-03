from datetime import datetime, timedelta
from typing import Union
from jose import jwt
from jose.constants import ALGORITHMS
from hashlib import pbkdf2_hmac
import base64
import os

from sqlalchemy import UUID
from app.core.config import settings

# Configurações
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = "HS256"
SALT_SIZE = 16
ITERATIONS = 100000  # Número de iterações para o PBKDF2

def create_access_token(subject: Union[str, UUID], expires_delta: timedelta = None) -> str:
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode = {"exp": expire, "sub": str(subject)}  # Garante que subject seja string
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)

def get_password_hash(password: str) -> str:
    """Gera um hash de senha usando PBKDF2-HMAC-SHA256"""
    salt = os.urandom(SALT_SIZE)
    key = pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt,
        ITERATIONS
    )
    # Armazenamos salt+hash em formato base64
    return base64.b64encode(salt + key).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica se a senha corresponde ao hash"""
    decoded = base64.b64decode(hashed_password)
    salt = decoded[:SALT_SIZE]
    stored_key = decoded[SALT_SIZE:]
    
    new_key = pbkdf2_hmac(
        'sha256',
        plain_password.encode('utf-8'),
        salt,
        ITERATIONS
    )
    return new_key == stored_key