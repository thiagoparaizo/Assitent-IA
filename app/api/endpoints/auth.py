# app/api/endpoints/auth.py
from datetime import datetime, timedelta
from typing import Any
import uuid

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, get_db
from app.core.config import settings
from app.core.security import create_access_token, get_password_hash, verify_password
from app.db.init_db import init_db 
from app.db.models.user import User
from app.schemas.token import Token
from app.schemas.user import UserCreate, UserResponse

router = APIRouter()

@router.post("/login", response_model=Token)
def login_access_token(
    db: Session = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()
) -> Any:
    """
    OAuth2 compatible token login, get an access token for future requests
    """
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    elif not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return {
        "access_token": create_access_token(
            str(user.id), expires_delta=access_token_expires
        ),
        "token_type": "bearer",
    }

@router.post("/register", response_model=UserResponse)
def register_user(
    *,
    db: Session = Depends(get_db),
    user_in: UserCreate,
) -> Any:
    """
    Register a new user.
    """
    # Check if email already exists
    user = db.query(User).filter(User.email == user_in.email).first()
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system.",
        )
    
    # Create new user
    user = User(
        id=uuid.uuid4(),
        email=user_in.email,
        full_name=user_in.full_name,
        tenant_id=user_in.tenant_id,
        is_active=True,
        is_superuser=False,
    )
    user.set_password(user_in.password)
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return user

@router.get("/me", response_model=UserResponse)
def read_users_me(
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get current user.
    """
    return current_user.to_dict()

# Add this to app/api/endpoints/auth.py

@router.post("/change-password")
def change_password(
    current_password: str = Body(...),
    new_password: str = Body(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Change current user password.
    """
    if not current_user.verify_password(current_password):
        raise HTTPException(status_code=400, detail="Incorrect password")
    
    # Update password
    current_user.set_password(new_password)
    db.add(current_user)
    db.commit()
    
    return {"message": "Password updated successfully"}


@router.get("/init_database")
def init_database():
    """
    Initialize the database.
    """
    init_db()
    
@router.get("/create-test-user")
def create_test_user(db: Session = Depends(get_db)):
    print("Creating test user...")
    test_user = User(
        id=uuid.uuid4(),
        email="user@gmail.com",
        hashed_password=get_password_hash("password"),
        full_name="Usuário de Teste",
        is_active=True,
        is_superuser=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    admin_user = User(
        id=uuid.uuid4(),
        email="admin@gmail.com",
        hashed_password=get_password_hash("password"),
        full_name="Usuário ADMIN de Teste",
        is_active=True,
        is_superuser=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    
    try:
        db.add(test_user)
        db.commit()
        db.refresh(test_user)
        print(f"Usuário TEST criado com ID: {test_user.id}")
        
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
        print(f"Usuário ADMIN criado com ID: {admin_user.id}")
    except Exception as e:
        db.rollback()
        print(f"Erro: {e}")
    finally:
        db.close()
    
    
    return {
        "message": "Usuário de teste criado com sucesso",
        "user_id": str(test_user.id),
        "email": test_user.email
    }


@router.post("/test-token", response_model=UserResponse)
def test_token(current_user: User = Depends(get_current_active_user)) -> Any:
    """
    Test access token.
    """
    return current_user.to_dict()