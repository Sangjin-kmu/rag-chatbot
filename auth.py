from fastapi import HTTPException, Header
from jose import jwt, JWTError
from google.oauth2 import id_token
from google.auth.transport import requests
from config import settings
from typing import Optional
import time

def verify_google_token(credential: str) -> Optional[dict]:
    """Google ID 토큰 검증"""
    try:
        idinfo = id_token.verify_oauth2_token(
            credential,
            requests.Request(),
            settings.google_client_id
        )
        
        return {
            "email": idinfo.get("email"),
            "name": idinfo.get("name"),
            "picture": idinfo.get("picture")
        }
    except Exception as e:
        print(f"Google token verification failed: {e}")
        return None

def create_token(user_info: dict) -> str:
    """JWT 토큰 생성"""
    payload = {
        "email": user_info.get("email"),
        "name": user_info.get("name"),
        "exp": int(time.time()) + 86400 * 7  # 7일
    }
    
    token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    return token

def verify_token(authorization: str = Header(None)) -> dict:
    """JWT 토큰 검증"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization format")
    
    token = authorization.replace("Bearer ", "")
    
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def verify_admin(user: dict = None) -> dict:
    """관리자 권한 검증"""
    if not user:
        from fastapi import Depends
        user = Depends(verify_token)
    
    admin_emails = [e.strip() for e in settings.doc_admin_emails.split(",")]
    
    if user.get("email") not in admin_emails:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return user
