# app/api/endpoints/token_limits.py
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from app.api.deps import get_db, get_current_active_user, get_current_active_superuser, get_tenant_id
from app.db.models.token_usage import TokenUsageLimit, TokenUsageLog, TokenUsageAlert
from app.db.models.user import User
from app.db.models.tenant import Tenant
from app.schemas.token_usage import (
    TokenUsageLimitCreate, TokenUsageLimitUpdate, TokenUsageLimitResponse,
    TokenUsageLogResponse, TokenUsageSummary, TokenUsageAlertResponse
)
from app.services.token_counter import TokenCounterService

router = APIRouter()

import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("app.api.endpoints.token_limits")

# Endpoints para gerenciamento de limites
@router.get("/limits", response_model=List[TokenUsageLimitResponse])
async def get_token_limits(
    tenant_id: Optional[int] = None,
    agent_id: Optional[str] = None, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Obtém limites de uso de tokens configurados.
    Os superusuários podem ver limites de qualquer tenant ou agente.
    Os usuários normais só podem ver limites de seu próprio tenant.
    """
    # Verificar permissões
    if not current_user.is_superuser and (
        (tenant_id and tenant_id != current_user.tenant_id) or not tenant_id
    ):
        # Se não for superuser, forçar tenant_id para o do usuário
        tenant_id = current_user.tenant_id
    
    # Construir consulta
    query = db.query(TokenUsageLimit)
    
    if tenant_id:
        query = query.filter(TokenUsageLimit.tenant_id == tenant_id)
    
    if agent_id:
        query = query.filter(TokenUsageLimit.agent_id == agent_id)
    
    # Executar consulta
    limits = query.all()
    return limits

@router.post("/limits", response_model=TokenUsageLimitResponse)
async def create_token_limit(
    limit: TokenUsageLimitCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Cria um novo limite de uso de tokens.
    Superusuários podem criar limites para qualquer tenant ou agente.
    Usuários normais só podem criar limites para seu próprio tenant.
    """
    # Verificar permissões
    if not current_user.is_superuser and limit.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=403,
            detail="Sem permissão para criar limites para este tenant"
        )
    
    # Verificar se já existe um limite para este tenant/agente
    existing = None
    
    if limit.agent_id:
        existing = db.query(TokenUsageLimit).filter(
            TokenUsageLimit.agent_id == limit.agent_id
        ).first()
    elif limit.tenant_id:
        existing = db.query(TokenUsageLimit).filter(
            TokenUsageLimit.tenant_id == limit.tenant_id,
            TokenUsageLimit.agent_id == None
        ).first()
    
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Já existe um limite configurado para este tenant/agente"
        )
    
    # Criar novo limite
    db_limit = TokenUsageLimit(**limit.dict())
    db.add(db_limit)
    db.commit()
    db.refresh(db_limit)
    
    return db_limit

@router.put("/limits/{limit_id}", response_model=TokenUsageLimitResponse)
async def update_token_limit(
    limit_update: TokenUsageLimitUpdate,
    limit_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Atualiza um limite de uso de tokens existente.
    Superusuários podem atualizar qualquer limite.
    Usuários normais só podem atualizar limites de seu próprio tenant.
    """
    # Buscar limite existente
    limit = db.query(TokenUsageLimit).filter(TokenUsageLimit.id == limit_id).first()
    
    if not limit:
        raise HTTPException(status_code=404, detail="Limite não encontrado")
    
    # Verificar permissões
    if not current_user.is_superuser and limit.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=403,
            detail="Sem permissão para atualizar este limite"
        )
    
    # Atualizar campos
    for field, value in limit_update.dict(exclude_unset=True).items():
        setattr(limit, field, value)
    
    db.commit()
    db.refresh(limit)
    
    return limit

@router.delete("/limits/{limit_id}")
async def delete_token_limit(
    limit_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Remove um limite de uso de tokens.
    Superusuários podem remover qualquer limite.
    Usuários normais só podem remover limites de seu próprio tenant.
    """
    limit = db.query(TokenUsageLimit).filter(TokenUsageLimit.id == limit_id).first()
    
    if not limit:
        raise HTTPException(status_code=404, detail="Limite não encontrado")
    
    # Verificar permissões
    if not current_user.is_superuser and limit.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=403,
            detail="Sem permissão para remover este limite"
        )
    
    db.delete(limit)
    db.commit()
    
    return {"message": "Limite removido com sucesso"}

# Endpoints para visualização de uso
@router.get("/usage", response_model=List[TokenUsageSummary])
async def get_token_usage(
    tenant_id: Optional[int] = None,
    agent_id: Optional[str] = None,
    period: str = Query("monthly", regex="^(daily|monthly|yearly)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Obtém um resumo do uso de tokens.
    Superusuários podem ver o uso de qualquer tenant ou agente.
    Usuários normais só podem ver o uso de seu próprio tenant.
    """
    # Verificar permissões
    if not current_user.is_superuser:
        # Se não for superuser, forçar tenant_id para o do usuário
        tenant_id = current_user.tenant_id
    
    # Inicializar serviço
    token_service = TokenCounterService(db)
    
    # Obter resumo
    summaries = await token_service.get_token_usage_summary(
        tenant_id=tenant_id,
        agent_id=agent_id,
        period=period
    )
    
    return summaries

@router.get("/alerts", response_model=List[TokenUsageAlertResponse])
async def get_token_alerts(
    tenant_id: Optional[int] = None,
    agent_id: Optional[str] = None,
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Obtém alertas de uso de tokens.
    Superusuários podem ver alertas de qualquer tenant ou agente.
    Usuários normais só podem ver alertas de seu próprio tenant.
    """
    # Verificar permissões
    if not current_user.is_superuser:
        # Se não for superuser, forçar tenant_id para o do usuário
        tenant_id = current_user.tenant_id
    
    # Construir consulta
    query = db.query(TokenUsageAlert)
    
    if tenant_id:
        query = query.filter(TokenUsageAlert.tenant_id == tenant_id)
    
    if agent_id:
        query = query.filter(TokenUsageAlert.agent_id == agent_id)
    
    # Ordenar por data de criação (mais recentes primeiro) e limitar resultados
    alerts = query.order_by(TokenUsageAlert.created_at.desc()).limit(limit).all()
    
    # Adicionar informações adicionais
    result = []
    for alert in alerts:
        alert_dict = alert.__dict__.copy()
        
        # Adicionar nome do tenant
        if alert.tenant_id:
            tenant = db.query(Tenant).filter(Tenant.id == alert.tenant_id).first()
            if tenant:
                alert_dict["tenant_name"] = tenant.name
        
        # Adicionar nome do agente
        if alert.agent_id:
            from app.db.models.agent import Agent
            agent = db.query(Agent).filter(Agent.id == alert.agent_id).first()
            if agent:
                alert_dict["agent_name"] = agent.name
        
        result.append(alert_dict)
    
    return result