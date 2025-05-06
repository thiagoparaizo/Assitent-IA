from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from app.api.deps import get_db, get_current_active_user, get_current_active_superuser
from app.db.models.tenant import Tenant
from app.db.models.user import User
from app.schemas.tenant import TenantCreate, TenantUpdate, TenantResponse

router = APIRouter()

@router.get("/", response_model=List[TenantResponse])
def read_tenants(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser), # TODO: implementar 
):
    """
    Retrieve all tenants (superuser only).
    """
    tenants = db.query(Tenant).offset(skip).limit(limit).all()
    return tenants

@router.post("/", response_model=TenantResponse)
def create_tenant(
    tenant: TenantCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser), # TODO: implementar 
):
    """
    Create a new tenant (superuser only).
    """
    # Check if tenant with same name already exists
    db_tenant = db.query(Tenant).filter(Tenant.name == tenant.name).first()
    if db_tenant:
        raise HTTPException(status_code=400, detail="Tenant with this name already exists")
    
    # Create new tenant
    db_tenant = Tenant(
        name=tenant.name,
        description=tenant.description,
        is_active=tenant.is_active
    )
    db.add(db_tenant)
    db.commit()
    db.refresh(db_tenant)
    return db_tenant

@router.get("/{tenant_id}", response_model=TenantResponse)
def read_tenant(
    tenant_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
     current_user: User = Depends(get_current_active_user), # TODO: implementar 
):
    """
    Get a specific tenant by ID.
    """
    # Regular users can only access their own tenant
    if not current_user.is_superuser and current_user.tenant_id != int(tenant_id):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Tenant with ID {tenant_id} not found")
    
    return tenant

@router.put("/{tenant_id}", response_model=TenantResponse)
def update_tenant(
    tenant_update: TenantUpdate,
    tenant_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser), # TODO: implementar 
):
    """
    Update a tenant (superuser only).
    """
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Tenant with ID {tenant_id} not found")
    
    # Update tenant fields
    for field, value in tenant_update.dict(exclude_unset=True).items():
        setattr(tenant, field, value)
    
    db.commit()
    db.refresh(tenant)
    return tenant

@router.delete("/{tenant_id}")
def delete_tenant(
    tenant_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser), # TODO: implementar 
):
    """
    Delete a tenant (superuser only).
    """
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Tenant with ID {tenant_id} not found")
    
    # Delete the tenant (cascading will handle related records)
    db.delete(tenant)
    db.commit()
    
    return {"message": f"Tenant {tenant_id} successfully deleted"}

@router.get("/{tenant_id}/users", response_model=List[dict])
def read_tenant_users(
    tenant_id: int = Path(..., ge=1),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user), # TODO: implementar 
):
    """
    Get all users for a specific tenant.
    """
    # Regular users can only access their own tenant
    if not current_user.is_superuser and current_user.tenant_id != int(tenant_id):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    # Check if tenant exists
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Tenant with ID {tenant_id} not found")
    
    # Get tenant users
    users = db.query(User).filter(User.tenant_id == tenant_id).offset(skip).limit(limit).all()
    
    # Convert to dictionaries since we're not using a full user schema here
    user_list = []
    for user in users:
        user_list.append({
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "is_active": user.is_active,
            "is_superuser": user.is_superuser,
            "created_at": user.created_at,
            "updated_at": user.updated_at
        })
    
    return user_list

@router.get("/{tenant_id}/users/count")
def count_tenant_users(
    tenant_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user), # TODO: implementar 
):
    """
    Count users for a specific tenant.
    """
    # Regular users can only access their own tenant
    if not current_user.is_superuser and current_user.tenant_id != int(tenant_id):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    # Check if tenant exists
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Tenant with ID {tenant_id} not found")
    
    # Count tenant users
    user_count = db.query(func.count(User.id)).filter(User.tenant_id == tenant_id).scalar()
    
    return {"count": user_count}