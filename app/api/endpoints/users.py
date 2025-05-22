# app/api/endpoints/users.py
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from app.api.deps import get_db, get_current_active_user, get_current_active_superuser
from app.db.models.user import User
from app.db.models.tenant import Tenant
from app.schemas.user import UserCreate, UserUpdate, UserResponse

router = APIRouter()

@router.get("/", response_model=List[UserResponse])
def read_users(
    skip: int = 0,
    limit: int = 100,
    tenant_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Retrieve users. Superusers can see all users, regular users only see users from their tenant.
    """
    query = db.query(User)
    
    if not current_user.is_superuser:
        # Regular users can only see users from their own tenant
        if current_user.tenant_id is None:
            raise HTTPException(status_code=403, detail="User not associated with any tenant")
        query = query.filter(User.tenant_id == current_user.tenant_id)
    elif tenant_id is not None:
        # Superuser filtering by specific tenant
        query = query.filter(User.tenant_id == tenant_id)
    
    users = query.offset(skip).limit(limit).all()
    return [user.to_dict() for user in users]

@router.post("/", response_model=UserResponse)
def create_user(
    user: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
):
    """
    Create a new user (superuser only).
    """
    # Check if user with same email already exists
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="User with this email already exists")
    
    # Verify tenant exists if tenant_id is provided
    if user.tenant_id:
        tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
        if not tenant:
            raise HTTPException(status_code=400, detail="Tenant not found")
    
    # Create new user
    import uuid
    from datetime import datetime
    
    db_user = User(
        id=uuid.uuid4(),
        email=user.email,
        full_name=user.full_name,
        tenant_id=user.tenant_id,
        is_active=True,
        is_superuser=user.is_superuser,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db_user.set_password(user.password)
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return db_user.to_dict()

@router.get("/{user_id}", response_model=UserResponse)
def read_user(
    user_id: str = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get a specific user by ID.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User with ID {user_id} not found")
    
    # Check permissions
    if not current_user.is_superuser:
        if current_user.id != user.id and current_user.tenant_id != user.tenant_id:
            raise HTTPException(status_code=403, detail="Not enough permissions")
    
    return user.to_dict()

@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_update: UserUpdate,
    user_id: str = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Update a user. Users can update themselves, superusers can update anyone.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User with ID {user_id} not found")
    
    # Check permissions
    if not current_user.is_superuser and current_user.id != user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    # Update user fields
    update_data = user_update.dict(exclude_unset=True)
    
    # Only superusers can change certain fields
    if not current_user.is_superuser:
        restricted_fields = ['is_superuser', 'tenant_id', 'is_active']
        for field in restricted_fields:
            if field in update_data:
                del update_data[field]
    
    # Verify tenant exists if tenant_id is being changed
    if 'tenant_id' in update_data and update_data['tenant_id']:
        tenant = db.query(Tenant).filter(Tenant.id == update_data['tenant_id']).first()
        if not tenant:
            raise HTTPException(status_code=400, detail="Tenant not found")
    
    # Check if email is being changed and if it already exists
    if 'email' in update_data and update_data['email'] != user.email:
        existing_user = db.query(User).filter(User.email == update_data['email']).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="User with this email already exists")
    
    # Update fields
    for field, value in update_data.items():
        if field == 'password' and value:
            user.set_password(value)
        elif hasattr(user, field):
            setattr(user, field, value)
    
    from datetime import datetime
    user.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(user)
    
    return user.to_dict()

@router.delete("/{user_id}")
def delete_user(
    user_id: str = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
):
    """
    Delete a user (superuser only).
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User with ID {user_id} not found")
    
    # Prevent deleting yourself
    if current_user.id == user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    
    # Delete the user
    db.delete(user)
    db.commit()
    
    return {"message": f"User {user_id} successfully deleted"}

@router.put("/{user_id}/activate")
def activate_user(
    user_id: str = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
):
    """
    Activate a user (superuser only).
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User with ID {user_id} not found")
    
    user.is_active = True
    from datetime import datetime
    user.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(user)
    
    return {"message": f"User {user_id} activated successfully"}

@router.put("/{user_id}/deactivate")
def deactivate_user(
    user_id: str = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
):
    """
    Deactivate a user (superuser only).
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User with ID {user_id} not found")
    
    # Prevent deactivating yourself
    if current_user.id == user.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")
    
    user.is_active = False
    from datetime import datetime
    user.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(user)
    
    return {"message": f"User {user_id} deactivated successfully"}

@router.post("/{user_id}/reset-password")
def reset_user_password(
    user_id: str = Path(...),
    new_password: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
):
    """
    Reset a user's password (superuser only).
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User with ID {user_id} not found")
    
    user.set_password(new_password)
    from datetime import datetime
    user.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(user)
    
    return {"message": f"Password reset successfully for user {user_id}"}

@router.get("/tenant/{tenant_id}/count")
def count_tenant_users(
    tenant_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Count users for a specific tenant.
    """
    # Regular users can only access their own tenant
    if not current_user.is_superuser and current_user.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    # Check if tenant exists
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Tenant with ID {tenant_id} not found")
    
    # Count tenant users
    user_count = db.query(func.count(User.id)).filter(User.tenant_id == tenant_id).scalar()
    
    return {"count": user_count}