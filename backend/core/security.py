from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import create_client, Client
from core.config import settings
import asyncio
import time
import os

# HTTPBearer extracts the "Authorization: Bearer <token>" header
security = HTTPBearer()

# Token Cache: token -> (user_object, expiry_timestamp)
_token_cache = {}
CACHE_EXPIRY_SECONDS = 300  # Cache verified tokens for 5 minutes

def get_cached_user(token: str):
    now = time.time()
    if token in _token_cache:
        user, expiry = _token_cache[token]
        if now < expiry:
            return user
        else:
            del _token_cache[token]
    return None

def set_cached_user(token: str, user):
    _token_cache[token] = (user, time.time() + CACHE_EXPIRY_SECONDS)

async def get_supabase_client(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Client:
    """
    Verifies the Supabase JWT (using cache if available), authenticates the client session, and returns the client.
    """
    token = credentials.credentials
    try:
        supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        
        if token == "dev-token" and not os.getenv("VERCEL"):
            class MockUser:
                id = "747e12b2-4a5d-47ee-98d9-fa71a714b9ad"
                email = "tansx1007@gmail.com"
            supabase.user = MockUser()
            return supabase
            
        # Check cache first
        user = get_cached_user(token)
        if user is None:
            # Run the synchronous SDK call in a separate thread pool
            user_response = await asyncio.to_thread(supabase.auth.get_user, token)
            user = user_response.user
            if not user or not user.id:
                raise ValueError("No user or user ID found in token")
            set_cached_user(token, user)
        
        # Authenticate Postgrest query with the user's token
        supabase.postgrest.auth(token)
        supabase.user = user
        return supabase
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """
    Verifies the Supabase JWT and returns the user's UID (UUID) string.
    """
    token = credentials.credentials
    try:
        if token == "dev-token" and not os.getenv("VERCEL"):
            return "747e12b2-4a5d-47ee-98d9-fa71a714b9ad"
            
        user = get_cached_user(token)
        if user is not None:
            return user.id
            
        supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        user_response = await asyncio.to_thread(supabase.auth.get_user, token)
        user = user_response.user
        if not user or not user.id:
            raise ValueError("No user or user ID found in token")
        set_cached_user(token, user)
        return user.id
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
