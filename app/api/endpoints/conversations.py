# Adicionar ao arquivo app/api/endpoints/conversations.py

from fastapi import APIRouter, Depends, HTTPException, Body, Query
from typing import List, Dict, Any, Optional

from app.services.orchestrator import AgentOrchestrator
from app.api.deps import get_tenant_id, get_enhanced_orchestrator

router = APIRouter()

@router.post("/")
async def start_conversation(
    user_id: str = Body(...),
    tenant_id: str = Depends(get_tenant_id),
    orchestrator: AgentOrchestrator = Depends(get_enhanced_orchestrator)
):
    """
    Inicia uma nova conversa com o sistema multiagente.
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
    orchestrator: AgentOrchestrator = Depends(get_enhanced_orchestrator)
):
    """
    Envia uma mensagem para uma conversa existente.
    """
    try:
        result = await orchestrator.process_message(conversation_id, message)
        
        # Check for errors
        if "error" in result:
            if result["error"] == "max_length_exceeded":
                raise HTTPException(status_code=400, detail="Conversation maximum length exceeded")
            elif result["error"] == "conversation_timeout":
                raise HTTPException(status_code=400, detail="Conversation timed out due to inactivity")
            else:
                raise HTTPException(status_code=500, detail=result["error"])
                
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    tenant_id: str = Depends(get_tenant_id),
    orchestrator: AgentOrchestrator = Depends(get_enhanced_orchestrator)
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
            "last_updated": state.last_updated,
            "metadata": state.metadata
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{conversation_id}/summary")
async def get_conversation_summary(
    conversation_id: str,
    tenant_id: str = Depends(get_tenant_id),
    orchestrator: AgentOrchestrator = Depends(get_enhanced_orchestrator)
):
    """
    Obtém um resumo da conversa.
    """
    try:
        state = await orchestrator.get_conversation_state(conversation_id)
        
        if not state:
            raise HTTPException(status_code=404, detail=f"Conversa {conversation_id} não encontrada")
        
        if state.tenant_id != tenant_id:
            raise HTTPException(status_code=403, detail="Sem permissão para acessar esta conversa")
        
        # Check if there's a recent summary
        if "last_summary" in state.metadata:
            summary = state.metadata["last_summary"]
            return {
                "conversation_id": state.conversation_id,
                "summary": summary,
                "generated_at": summary.get("generated_at")
            }
        
        # Generate a new summary if needed
        if orchestrator.memory_service:
            summary = await orchestrator.memory_service.generate_conversation_summary(
                conversation_id=state.conversation_id,
                tenant_id=state.tenant_id,
                user_id=state.user_id,
                messages=state.history
            )
            
            if summary:
                return {
                    "conversation_id": state.conversation_id,
                    "brief_summary": summary.brief_summary,
                    "detailed_summary": summary.detailed_summary,
                    "sentiment": summary.sentiment,
                    "key_points": summary.key_points,
                    "entities": summary.entities,
                    "generated_at": summary.created_at
                }
        
        # Fall back to basic summary if memory service is unavailable
        return {
            "conversation_id": state.conversation_id,
            "message_count": len(state.history),
            "last_updated": state.last_updated,
            "summary": "No detailed summary available"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/user/{user_id}/profile")
async def get_user_profile(
    user_id: str,
    tenant_id: str = Depends(get_tenant_id),
    orchestrator: AgentOrchestrator = Depends(get_enhanced_orchestrator)
):
    """
    Obtém o perfil do usuário baseado no histórico de memórias.
    """
    try:
        if not orchestrator.memory_service:
            raise HTTPException(status_code=400, detail="Memory service is not enabled")
        
        profile = await orchestrator.get_user_profile(tenant_id, user_id)
        return profile
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/")
async def list_conversations(
    tenant_id: str = Depends(get_tenant_id),
    user_id: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    orchestrator: AgentOrchestrator = Depends(get_enhanced_orchestrator)
):
    """
    Lista conversas disponíveis.
    """
    try:
        # This would normally search the database
        # For now, return a simpler implementation based on Redis
        
        # Create a pattern to search for conversation keys
        if user_id:
            # Search for specific user's conversations
            conversations = await orchestrator.list_conversations_by_user(tenant_id, user_id, limit)
        else:
            # Search for all tenant conversations
            conversations = await orchestrator.list_conversations_by_tenant(tenant_id, limit)
        
        return {
            "conversations": conversations,
            "count": len(conversations)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))