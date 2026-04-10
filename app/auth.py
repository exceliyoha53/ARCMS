import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def hash_password(password: str) -> str:
    """
     Hashes a plain text password using bcrypt.
     One-way hash - original password cannot be recovered.

     Parameters:
        password (str): Raw password from registration

    Returns:
        str: bcrypt hash to store in database
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plain text password against a stored bcrypt hash.

    Parameters:
        plain_password (str): Raw password from login request
        hashed_password (str): bcrypt hash from database

    Returns:
        bool: True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Creates a signed JWT access token.
    Stores email and role in the payload so every request carries identity and permissions.

    Parameters:
        data (dict): Payload to encode — typically {"sub": email, "role": role}
        expires_delta (Optional[timedelta]): Custom expiry duration

    Returns:
        str: Signed JWT token string
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    logger.info(f"Token created for: {data.get('sub')} role: {data.get('role')}")
    return token


def decode_access_token(token: str) -> Optional[dict]:
    """
    Decodes and verifies a JWT token.
    Returns payload if valid, None if expired or tampered.

    Parameters:
        token (str): JWT string from request header

    Returns:
        Optional[dict]: Decoded payload or None if invalid
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        logger.warning(f"Invalid token: {e}")
        return None


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """
    FastAPI dependency — extracts and validates current user from JWT.
    Inject into any protected endpoint with: Depends(get_current_user)

    Parameters:
        token (str): Auto-extracted from Authorization header

    Returns:
        dict: Contains email and role of authenticated user

    Raises:
        HTTPException 401: If token is missing, expired, or invalid
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception
    email: str = payload.get("sub")
    role: str = payload.get("role")

    if email is None or role is None:
        raise credentials_exception

    return {"email": email, "role": role}


def require_role(*allowed_roles: str):
    """
    FastAPI dependency factory that restricts endpoints to specific roles.
    Returns a dependency function that checks the current user's role.
    Usage: Depends(require_role("lecturer", "hod"))

    Parameters:
        *allowed_roles (str): One or more roles that can access the endpoint

    Returns:
        Callable: A FastAPI dependency that enforces role access

    Raises:
        HTTPException 403: If the user's role is not in allowed_roles
    """

    async def role_checker(current_user: dict = Depends(get_current_user)) -> dict:
        if current_user["role"] not in allowed_roles:
            logger.warning(
                f"Access denied for {current_user['email']}"
                f"(role: {current_user['role']}) - required: {allowed_roles}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access restricted. Required role: {', '.join(allowed_roles)}",
            )
        return current_user

    return role_checker


require_student = require_role("student")
require_lecturer = require_role(
    "lecturer", "hod", "exam_officer"
)  # hod and exam officer can also upload
require_hod = require_role("hod")
require_exam_officer = require_role("exam_officer", "hod")
require_registrar = require_role("registrar")
require_staff = require_role("lecturer", "hod", "exam_officer", "registrar")
