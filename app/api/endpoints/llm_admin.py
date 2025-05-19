# app/api/endpoints/llm_admin.py
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_active_superuser
from app.db.models.user import User
from app.db.models.llm_provider import LLMProvider
from app.db.models.llm_model import LLMModel
from app.schemas.llm import (
    LLMProviderCreate, LLMProviderUpdate, LLMProviderResponse,
    LLMModelCreate, LLMModelUpdate, LLMModelResponse
)

router = APIRouter()

# Endpoints para gerenciamento de provedores LLM
@router.get("/providers", response_model=List[LLMProviderResponse])
def get_providers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
):
    """Lista todos os provedores LLM."""
    providers = db.query(LLMProvider).all()
    return providers

@router.post("/providers", response_model=LLMProviderResponse)
def create_provider(
    provider: LLMProviderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
):
    """Cria um novo provedor LLM."""
    db_provider = LLMProvider(**provider.dict())
    db.add(db_provider)
    db.commit()
    db.refresh(db_provider)
    return db_provider

# Endpoints similares para edição e exclusão de provedores...

# Endpoints para gerenciamento de modelos LLM
@router.get("/models", response_model=List[LLMModelResponse])
def get_models(
    provider_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
):
    """Lista todos os modelos LLM, opcionalmente filtrados por provedor."""
    query = db.query(LLMModel)
    if provider_id:
        query = query.filter(LLMModel.provider_id == provider_id)
    
    models = query.all()
    
    # Adicionar nome do provedor para UI
    result = []
    for model in models:
        provider = db.query(LLMProvider).filter(LLMProvider.id == model.provider_id).first()
        model_dict = model.__dict__.copy()
        model_dict["provider_name"] = provider.name if provider else "Unknown"
        result.append(model_dict)
    
    return result

@router.post("/models", response_model=LLMModelResponse)
def create_model(
    model: LLMModelCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
):
    """Cria um novo modelo LLM."""
    # Verificar se o provedor existe
    provider = db.query(LLMProvider).filter(LLMProvider.id == model.provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    
    db_model = LLMModel(**model.dict())
    db.add(db_model)
    db.commit()
    db.refresh(db_model)
    
    # Adicionar nome do provedor para response
    result = db_model.__dict__.copy()
    result["provider_name"] = provider.name
    
    return result

@router.get("/models/{model_id}", response_model=LLMModelResponse)
def get_model(
    model_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
):
    """Obtém detalhes de um modelo LLM específico."""
    model = db.query(LLMModel).filter(LLMModel.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="Modelo LLM não encontrado")
    return model

@router.put("/models/{model_id}", response_model=LLMModelResponse)
def update_model(
    model_update: LLMModelUpdate,
    model_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
):
    """Atualiza um modelo LLM."""
    model = db.query(LLMModel).filter(LLMModel.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="Modelo LLM não encontrado")
    
    # Atualizar os campos
    for field, value in model_update.dict(exclude_unset=True).items():
        setattr(model, field, value)
    
    db.commit()
    db.refresh(model)
    return model

@router.delete("/models/{model_id}")
def delete_model(
    model_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
):
    """Remove um modelo LLM."""
    model = db.query(LLMModel).filter(LLMModel.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="Modelo LLM não encontrado")
    
    db.delete(model)
    db.commit()
    
    return {"message": "Modelo LLM removido com sucesso"}


@router.get("/providers/{provider_id}", response_model=LLMProviderResponse)
def get_provider(
    provider_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
):
    """Obtém detalhes de um provedor LLM específico."""
    provider = db.query(LLMProvider).filter(LLMProvider.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provedor LLM não encontrado")
    return provider

@router.put("/providers/{provider_id}", response_model=LLMProviderResponse)
def update_provider(
    provider_update: LLMProviderUpdate,
    provider_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
):
    """Atualiza um provedor LLM."""
    provider = db.query(LLMProvider).filter(LLMProvider.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provedor LLM não encontrado")
    
    # Atualizar os campos
    for field, value in provider_update.dict(exclude_unset=True).items():
        setattr(provider, field, value)
    
    db.commit()
    db.refresh(provider)
    return provider

@router.delete("/providers/{provider_id}")
def delete_provider(
    provider_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
):
    """Remove um provedor LLM."""
    provider = db.query(LLMProvider).filter(LLMProvider.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provedor LLM não encontrado")
    
    # Verificar se há modelos associados
    models_count = db.query(LLMModel).filter(LLMModel.provider_id == provider_id).count()
    
    # Exclui o provedor (e todos os modelos devido à relação cascade)
    db.delete(provider)
    db.commit()
    
    return {
        "message": f"Provedor LLM removido com sucesso, incluindo {models_count} modelos associados"
    }