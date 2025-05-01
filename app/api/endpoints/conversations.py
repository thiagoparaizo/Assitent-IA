# Adicionar ao arquivo app/api/endpoints/conversations.py

from fastapi import APIRouter, Depends, HTTPException, Body
from typing import List, Dict, Any, Optional

from app.services.orchestrator import AgentOrchestrator
from app.api.deps import get_tenant_id, get_orchestrator

router = APIRouter()

@router.post("/")
async def start_conversation(
    user_id: str = Body(...),
    tenant_id: str = Depends(get_tenant_id),
    orchestrator: AgentOrchestrator = Depends(get_orchestrator)
):
    """
    Inicia uma nova conversa.
    """
    try:
        conversation_id = await orchestrator.start_conversation(tenant_id, user_id)
        return {"conversation_id": conversation_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{conversation_id}/messages")
async def send_message(
    conversation_id: str,
    message: str = Body(..., embed=True),
    tenant_id: str = Depends(get_tenant_id),
    orchestrator: AgentOrchestrator = Depends(get_orchestrator)
):
    """
    Envia uma mensagem para uma conversa existente.
    """
    try:
        result = await orchestrator.process_message(conversation_id, message)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    tenant_id: str = Depends(get_tenant_id),
    orchestrator: AgentOrchestrator = Depends(get_orchestrator)
):
    """
    Obtém o histórico de uma conversa.
    """
    try:
        state = await orchestrator.get_conversation_state(conversation_id)
        
        if not state:
            raise HTTPException(status_code=404, detail=f"Conversa {conversation_id} não encontrada")
        
        if state.tenant_id != tenant_id:
            raise HTTPException(status_code=403, detail="Sem permissão para acessar esta conversa")
        
        return {
            "conversation_id": state.conversation_id,
            "tenant_id": state.tenant_id,
            "user_id": state.user_id,
            "current_agent_id": state.current_agent_id,
            "history": state.history,
            "last_updated": state.last_updated
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))