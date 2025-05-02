# app/routes/agents.py
from fastapi import APIRouter, Depends, HTTPException, Body
from typing import List, Dict, Any, Optional

from app.schemas import agent as schemas
from app.services.agent import AgentService, Agent, AgentType, AgentPrompt
from app.api.deps import get_tenant_id, get_agent_service

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])

@router.post("/", response_model=schemas.Agent)
async def create_agent(
    agent_data: Dict[str, Any] = Body(...),
    tenant_id: str = Depends(get_tenant_id),
    agent_service: AgentService = Depends(get_agent_service)
):
    """Cria um novo agente."""
    # Garantir que o tenant_id está correto
    agent_data["tenant_id"] = tenant_id
    
    try:
        agent = await agent_service.create_agent(agent_data)
        return agent
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/", response_model=List[schemas.Agent])
async def list_agents(
    tenant_id: str = Depends(get_tenant_id),
    agent_service: AgentService = Depends(get_agent_service),
    agent_type: Optional[str] = None
):
    """Lista os agentes de um tenant."""
    agents = await agent_service.get_agents_by_tenant(tenant_id)
    
    if agent_type:
        try:
            type_enum = AgentType(agent_type)
            agents = [a for a in agents if a.type == type_enum]
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Tipo de agente inválido: {agent_type}")
    
    return agents

@router.get("/{agent_id}", response_model=schemas.Agent)
async def get_agent(
    agent_id: str,
    tenant_id: str = Depends(get_tenant_id),
    agent_service: AgentService = Depends(get_agent_service)
):
    """Obtém um agente pelo ID."""
    agent = await agent_service.get_agent(agent_id)
    
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agente {agent_id} não encontrado")
    
    # Verificar se o agente pertence ao tenant
    if agent.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Sem permissão para acessar este agente")
    
    return agent

@router.put("/{agent_id}", response_model=schemas.AgentUpdate)
async def update_agent(
    agent_id: str,
    agent_data: Dict[str, Any] = Body(...),
    tenant_id: str = Depends(get_tenant_id),
    agent_service: AgentService = Depends(get_agent_service)
):
    """Atualiza um agente existente."""
    # Verificar se o agente existe e pertence ao tenant
    agent = await agent_service.get_agent(agent_id)
    
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agente {agent_id} não encontrado")
    
    if agent.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Sem permissão para atualizar este agente")
    
    # Garantir que o tenant_id não seja alterado
    agent_data["tenant_id"] = tenant_id
    
    try:
        updated_agent = await agent_service.update_agent(agent_id, agent_data)
        return updated_agent
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{agent_id}")
async def delete_agent(
    agent_id: str,
    tenant_id: str = Depends(get_tenant_id),
    agent_service: AgentService = Depends(get_agent_service)
):
    """Remove um agente."""
    # Verificar se o agente existe e pertence ao tenant
    agent = await agent_service.get_agent(agent_id)
    
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agente {agent_id} não encontrado")
    
    if agent.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Sem permissão para remover este agente")
    
    success = await agent_service.delete_agent(agent_id)
    
    if not success:
        raise HTTPException(status_code=500, detail="Falha ao remover agente")
    
    return {"message": "Agente removido com sucesso"}