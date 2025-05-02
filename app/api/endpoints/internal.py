from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models.tenant import Tenant
from app.db.models.user import User

router = APIRouter()

# Este router é para uso interno e não deve ser exposto publicamente
# Futuramente, poderá ter validação de requisições locais apenas

@router.get("/tenants/validate/{tenant_id}")
def validate_tenant(
    tenant_id: int,
    db: Session = Depends(get_db)
):
    """
    Valida se um tenant existe e está ativo.
    Este endpoint é para uso interno do WhatsApp Server.
    """
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id, Tenant.is_active == True).first()
    
    if not tenant:
        return {"exists": False, "is_active": False}
    
    return {"exists": True, "is_active": True, "name": tenant.name}


@router.get("/tenants/list")
def list_active_tenants(
    db: Session = Depends(get_db)
):
    """
    Lista todos os tenants ativos.
    Este endpoint é para uso interno do WhatsApp Server.
    """
    tenants = db.query(Tenant).filter(Tenant.is_active == True).all()
    
    result = []
    for tenant in tenants:
        result.append({
            "id": tenant.id,
            "name": tenant.name,
            "description": tenant.description
        })
    
    return result


@router.post("/webhooks/event")
async def process_webhook_event(
    event: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """
    Recebe eventos do WhatsApp Server e processa baseado na configuração de webhooks.
    Este endpoint é para uso interno do WhatsApp Server.
    """
    # Importar o processamento de webhook da implementação existente
    from app.api.endpoints.webhook import process_whatsapp_message
    
    # Processar o evento usando a lógica existente
    await process_whatsapp_message(event, None, db)
    
    return {"status": "processed"}