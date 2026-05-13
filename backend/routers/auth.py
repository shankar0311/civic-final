from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import timedelta
from typing import Annotated

from database import get_db
from models import User, UserRole
from schemas import UserCreate, UserResponse, Token
from utils.security import verify_password, get_password_hash, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
from jose import JWTError, jwt
from utils.security import SECRET_KEY, ALGORITHM
import os
import httpx
from fastapi.responses import RedirectResponse

router = APIRouter(prefix="/auth", tags=["auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: AsyncSession = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalars().first()
    if user is None:
        raise credentials_exception
    return user

@router.post("/register", response_model=UserResponse)
async def register(user: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == user.email))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_password = get_password_hash(user.password)
    new_user = User(
        email=user.email, 
        hashed_password=hashed_password,
        name=user.name,
        role=user.role
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user

@router.post("/login", response_model=Token)
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalars().first()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user

# Google OAuth Configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI", "http://localhost:8005/auth/google/callback")

@router.get("/google/login")
async def google_login():
    """Redirect to Google OAuth2 login"""
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Google Client ID not configured")
    
    return RedirectResponse(
        url=f"https://accounts.google.com/o/oauth2/auth?client_id={GOOGLE_CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}&scope=openid%20email%20profile"
    )

@router.get("/google/callback")
async def google_callback(code: str, db: AsyncSession = Depends(get_db)):
    """Handle Google OAuth2 callback"""
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="Google credentials not configured")

    async with httpx.AsyncClient() as client:
        # 1. Exchange code for token
        token_response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": REDIRECT_URI,
            },
        )
        
        if token_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to retrieve token from Google")
        
        token_data = token_response.json()
        access_token = token_data.get("access_token")
        
        # 2. Get user info
        user_info_response = await client.get(
            "https://www.googleapis.com/oauth2/v1/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        
        if user_info_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to retrieve user info from Google")
            
        user_info = user_info_response.json()
        email = user_info.get("email")
        name = user_info.get("name")
        
        if not email:
            raise HTTPException(status_code=400, detail="Email not found in Google account")

        # 3. Check if user exists or create new one
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalars().first()
        
        if not user:
            # Create new user with random password (since they use Google to login)
            # We use a secure random string that they won't know, effectively disabling password login
            # unless they do a "forgot password" flow later (if implemented)
            import secrets
            random_password = secrets.token_urlsafe(32)
            hashed_password = get_password_hash(random_password)
            
            user = User(
                email=email,
                name=name,
                hashed_password=hashed_password,
                role=UserRole.citizen # Default to citizen
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
            
        # 4. Create JWT token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        jwt_token = create_access_token(
            data={"sub": user.email}, expires_delta=access_token_expires
        )
        
        # 5. Redirect to frontend with token
        # We redirect to a special frontend route that will handle storing the token
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
        return RedirectResponse(url=f"{frontend_url}/auth/callback?token={jwt_token}&role={user.role.value}&email={user.email}&name={user.name}")
