import secrets
import string

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

MAX_BCRYPT_BYTES = 72


def verify_password(plain_password, hashed_password) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    if len(password.encode("utf-8")) > MAX_BCRYPT_BYTES:
        raise ValueError("Password too long")
    return pwd_context.hash(password)


def generate_password(length: int = 10) -> str:
    """Returns a random string of length"""
    alphabet = string.ascii_letters + string.digits
    password = "".join(secrets.choice(alphabet) for i in range(length))

    return password
