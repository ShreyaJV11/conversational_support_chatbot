import jwt
import time
import os
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, status, Header
from fastapi.security import OAuth2PasswordBearer
from app.core.redis_config import redis_client


SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("JWT_SECRET_KEY must be set in .env file")

# Load admin emails from environment variable
ADMIN_EMAILS = os.getenv("ADMIN_EMAILS", "").split(",")
ADMIN_EMAILS = [email.strip() for email in ADMIN_EMAILS if email.strip()]

if not ADMIN_EMAILS:
    print("⚠️  WARNING: No ADMIN_EMAILS configured. Admin endpoints will be inaccessible.")
    
ALGORITHM = "HS256"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def create_jwt_token(email: str):
    payload = {
        "sub": email,
        "exp": datetime.utcnow() + timedelta(hours=24)
    }

    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token


def verify_jwt_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        user_email = payload.get("sub") or payload.get("email")

        if user_email is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: Email missing"
            )

        return user_email

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired. Please login again."
        )

    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


def check_rate_limit(email: str):

    key = f"ticket_limit:{email}"
    current_count = redis_client.get(key)

    if current_count and int(current_count) >= 3:

        ttl = redis_client.ttl(key)
        hours_left = round(ttl / 3600, 1)

        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Daily ticket limit reached. Try again in {hours_left} hours."
        )

    if not current_count:
        redis_client.setex(key, 86400, 1)

    else:
        redis_client.incr(key)

    return True



def verify_admin_token(authorization: str = Header(None)):
    """
    Verify JWT token and check if user has admin privileges.
    Used as a dependency for admin-only endpoints.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format. Use: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = authorization.split(" ")[1]
    email = verify_jwt_token(token)
    
    
    if email not in ADMIN_EMAILS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required. Contact system administrator."
        )
    
    return {"email": email, "role": "admin"}


def create_admin_token(email: str):
    """
    Create JWT token for admin users with extended expiration.
    """
    if email not in ADMIN_EMAILS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized as admin"
        )
    
    payload = {
        "sub": email,
        "role": "admin",
        "exp": datetime.utcnow() + timedelta(hours=48)  # Longer expiration for admins
    }
    
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token
