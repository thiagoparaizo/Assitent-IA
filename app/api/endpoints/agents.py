# app/routes/agents.py

from fastapi import APIRouter, Depends, HTTPException, Body
from typing import List, Dict, Any, Optional

from sqlalchemy import select

from app.db.models.contact_control import ContactControl, ContactListType
from app.db.models.user import User
from app.schemas import agent as schemas
from app.schemas.contact_control import AgentContactConfig
from app.services.agent import AgentService, Agent, AgentType, AgentPrompt
from app.api.deps import get_current_active_user, get_tenant_id, get_agent_service

router = APIRouter()
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("app.api.endpoints.agents")

@router.post("/", response_model=schemas.Agent)
async def create_agent(
    agent_data: Dict[str, Any] = Body(...),
    tenant_id: str = Depends(get_tenant_id),
    agent_service: AgentService = Depends(get_agent_service),
    current_user: User = Depends(get_current_active_user),
    
):
    """Cria um novo agente."""
    # Garantir que o tenant_id está correto
    agent_data["tenant_id"] = tenant_id
    
    try:
        agent = await agent_service.create_agent(agent_data)
        return agent
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/list", response_model=List[schemas.Agent])
async def list_agents(
    tenant_id: int,
    agent_service: AgentService = Depends(get_agent_service),
    agent_type: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
):
    """Lista os agentes de um tenant."""
    agents = agent_service.get_agents_by_tenant(tenant_id)
    
    if agent_type:
        try:
            type_enum = AgentType(agent_type)
            agents = [a for a in agents if a.type == type_enum]
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Tipo de agente inválido: {agent_type}")
    
    return agents

@router.get("/", response_model=List[schemas.Agent])
async def list_agents(
    tenant_id: str = Depends(get_tenant_id),
    agent_service: AgentService = Depends(get_agent_service),
    agent_type: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
):
    """Lista os agentes de um tenant."""
    agents = agent_service.get_agents_by_tenant(tenant_id)
    
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
    tenant_id: int = Depends(get_tenant_id),
    agent_service: AgentService = Depends(get_agent_service),
    current_user: User = Depends(get_current_active_user),
):
    """Obtém um agente pelo ID."""
    agent = agent_service.get_agent(agent_id)
    
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agente {agent_id} não encontrado")
    
    # Verificar se o agente pertence ao tenant
    if agent.tenant_id != int(tenant_id):
        raise HTTPException(status_code=403, detail="Sem permissão para acessar este agente")
    
    return agent


@router.put("/{agent_id}", response_model=schemas.AgentUpdate)
async def update_agent(
    agent_id: str,
    agent_data: Dict[str, Any] = Body(...),
    tenant_id: str = Depends(get_tenant_id),
    agent_service: AgentService = Depends(get_agent_service),
    current_user: User = Depends(get_current_active_user),
):
    """Atualiza um agente existente."""
    # Verificar se o agente existe e pertence ao tenant
    agent = agent_service.get_agent(agent_id)
    
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agente {agent_id} não encontrado")
    
    if agent.tenant_id != int(tenant_id):
        raise HTTPException(status_code=403, detail="Sem permissão para atualizar este agente")
    
    # Garantir que o tenant_id não seja alterado
    agent_data["tenant_id"] = tenant_id
    
    # Garantir que os campos opcionais estejam inicializados corretamente
    if "specialties" in agent_data and agent_data["specialties"] is None:
        agent_data["specialties"] = []
        
    if "list_escalation_agent_ids" in agent_data and agent_data["list_escalation_agent_ids"] is None:
        agent_data["list_escalation_agent_ids"] = []
    
    # Processar a lista de agentes de escalação se presente
    if "list_escalation_agent_ids" in agent_data:
        # Validar que os IDs de agentes pertencem ao mesmo tenant
        for esc_agent_id in agent_data["list_escalation_agent_ids"]:
            esc_agent = agent_service.get_agent(esc_agent_id)
            if not esc_agent or esc_agent.tenant_id != int(tenant_id):
                raise HTTPException(
                    status_code=400, 
                    detail=f"Agente de escalação {esc_agent_id} não encontrado ou não pertence ao tenant"
                )
    
    try:
        updated_agent = agent_service.update_agent(agent_id, agent_data)
        return updated_agent
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/{agent_id}/status")
async def update_agent_status(
    agent_id: str,
    status_data: Dict[str, bool] = Body(...),
    tenant_id: str = Depends(get_tenant_id),
    agent_service: AgentService = Depends(get_agent_service),
    current_user: User = Depends(get_current_active_user),
):
    """Atualiza o status de um agente (ativo/inativo)."""
    # Verificar se o agente existe e pertence ao tenant
    agent = agent_service.get_agent(agent_id)
    
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agente {agent_id} não encontrado")
    
    if agent.tenant_id != int(tenant_id):
        raise HTTPException(status_code=403, detail="Sem permissão para atualizar este agente")
    
    # Atualizar status
    active = status_data.get("active", True)
    
    try:
        updated_agent = agent_service.update_agent_status(agent_id, active)
        return {"status": "success", "active": active}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{agent_id}")
async def delete_agent(
    agent_id: str,
    tenant_id: str = Depends(get_tenant_id),
    agent_service: AgentService = Depends(get_agent_service),
    current_user: User = Depends(get_current_active_user),
):
    """Remove um agente."""
    # Verificar se o agente existe e pertence ao tenant
    agent = agent_service.get_agent(agent_id)
    
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agente {agent_id} não encontrado")
    
    if agent.tenant_id != int(tenant_id):
        raise HTTPException(status_code=403, detail="Sem permissão para remover este agente")
    
    success = agent_service.delete_agent(agent_id)
    
    if not success:
        raise HTTPException(status_code=500, detail="Falha ao remover agente")
    
    return {"message": "Agente removido com sucesso"}


@router.post("/{agent_id}/device/{device_id}/contacts")
async def manage_agent_contacts(
    agent_id: str,
    device_id: int,
    config: AgentContactConfig,
    tenant_id: str = Depends(get_tenant_id),
    agent_service: AgentService = Depends(get_agent_service),
    current_user: User = Depends(get_current_active_user),
):
    """Gerencia a configuração de contatos para um agente em um dispositivo específico."""
    # Verificar permissões
    agent = agent_service.get_agent(agent_id)
    if not agent or agent.tenant_id != int(tenant_id):
        raise HTTPException(status_code=404, detail="Agente não encontrado")
    
    # Converter tipo de lista
    list_type = ContactListType.WHITELIST if config.default_behavior == "whitelist" else ContactListType.BLACKLIST
    
    # Atualizar lista de contatos
    result = await agent_service.manage_contact_list(
        agent_id=agent_id,
        device_id=device_id,
        contacts=config.contacts,
        list_type=list_type
    )
    
    if not result:
        raise HTTPException(status_code=400, detail="Falha ao atualizar lista de contatos")
    
    return {"status": "success", "message": "Lista de contatos atualizada com sucesso"}

@router.get("/{agent_id}/device/{device_id}/contacts")
async def get_agent_contacts(
    agent_id: str,
    device_id: int,
    tenant_id: str = Depends(get_tenant_id),
    agent_service: AgentService = Depends(get_agent_service),
    current_user: User = Depends(get_current_active_user),
):
    """Obtém a configuração de contatos para um agente em um dispositivo específico."""
    # Verificar permissões
    agent = agent_service.get_agent(agent_id)
    if not agent or agent.tenant_id != int(tenant_id):
        raise HTTPException(status_code=404, detail="Agente não encontrado")
    
    # Buscar todos os controles para este agente e dispositivo
    query = select(ContactControl).where(
        ContactControl.agent_id == agent_id,
        ContactControl.device_id == device_id
    )
    result = agent_service.db.execute(query)
    controls = result.scalars().all()
    
    # Agrupar por tipo
    whitelist = [c.contact_id for c in controls if c.list_type == ContactListType.WHITELIST]
    blacklist = [c.contact_id for c in controls if c.list_type == ContactListType.BLACKLIST]
    
    # Determinar comportamento padrão
    default_behavior = "whitelist" if whitelist else "blacklist"
    
    # Retornar lista ativa
    contacts = whitelist if whitelist else blacklist
    
    return {
        "agent_id": agent_id,
        "device_id": device_id,
        "default_behavior": default_behavior,
        "contacts": contacts
    }
   
   
@router.put("/{agent_id}/device/{device_id}/contacts/{contact_id}")
def add_contact_to_list(
    agent_id: str,
    device_id: int,
    contact_id: str,
    data: Dict[str, Any] = Body(...),
    tenant_id: str = Depends(get_tenant_id),
    agent_service: AgentService = Depends(get_agent_service),
    current_user: User = Depends(get_current_active_user),
):
    """Adiciona um contato à lista de um agente."""
    # Verificar permissões
    agent = agent_service.get_agent(agent_id)
    if not agent or agent.tenant_id != int(tenant_id):
        raise HTTPException(status_code=404, detail="Agente não encontrado")
    
    # Determinar o tipo de lista
    list_type = data.get("list_type", "blacklist")
    list_type_enum = ContactListType.WHITELIST if list_type == "whitelist" else ContactListType.BLACKLIST
    
    # Adicionar o contato à lista
    result = agent_service.add_contact_to_list(
        agent_id=agent_id,
        device_id=device_id,
        contact_id=contact_id,
        list_type=list_type_enum
    )
    
    if not result:
        raise HTTPException(status_code=400, detail="Falha ao adicionar contato à lista")
    
    return {"success": True, "message": "Contato adicionado com sucesso"} 
  
  
@router.delete("/{agent_id}/device/{device_id}/contacts/{contact_id}")
def remove_contact_from_list(
    agent_id: str,
    device_id: int,
    contact_id: str,
    tenant_id: str = Depends(get_tenant_id),
    agent_service: AgentService = Depends(get_agent_service),
    current_user: User = Depends(get_current_active_user),
):
    """Remove um contato da lista de um agente."""
    # Verificar permissões
    agent = agent_service.get_agent(agent_id)
    if not agent or agent.tenant_id != int(tenant_id):
        raise HTTPException(status_code=404, detail="Agente não encontrado")
    
    # Determinar o tipo de lista atual
    query = select(ContactControl).where(
        ContactControl.agent_id == agent_id,
        ContactControl.device_id == device_id,
        ContactControl.contact_id == contact_id
    )
    result = agent_service.db.execute(query)
    control = result.scalar_one_or_none()
    
    if not control:
        raise HTTPException(status_code=404, detail="Contato não encontrado na lista")
    
    # Remover o contato da lista
    success = agent_service.remove_contact_from_list(
        agent_id=agent_id,
        device_id=device_id,
        contact_id=contact_id,
        list_type=control.list_type
    )
    
    if not success:
        raise HTTPException(status_code=400, detail="Falha ao remover contato da lista")
    
    return {"success": True, "message": "Contato removido com sucesso"}
  
@router.get("/{agent_id}/devices")
async def get_agent_devices(
    agent_id: str,
    tenant_id: str = Depends(get_tenant_id),
    agent_service: AgentService = Depends(get_agent_service),
    current_user: User = Depends(get_current_active_user),
):
    """Obtém os dispositivos associados a um agente."""
    # Verificar se o agente pertence ao tenant
    agent = agent_service.get_agent(agent_id)
    
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agente {agent_id} não encontrado")
    
    if agent.tenant_id != int(tenant_id):
        raise HTTPException(status_code=403, detail="Sem permissão para acessar este agente")
    
    # Buscar dispositivos associados
    devices = await agent_service.get_devices_for_agent(agent_id)
    
    return devices

@router.post("/{agent_id}/device/{device_id}/assign")
async def assign_device_to_agent(
    agent_id: str,
    device_id: int,
    active: bool = Body(..., embed=True),
    tenant_id: str = Depends(get_tenant_id),
    agent_service: AgentService = Depends(get_agent_service),
    current_user: User = Depends(get_current_active_user),
):
    """Atribui ou desvincula um dispositivo de um agente."""
    # Verificar se o agente pertence ao tenant
    agent = agent_service.get_agent(agent_id)
    
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agente {agent_id} não encontrado")
    
    if agent.tenant_id != int(tenant_id):
        raise HTTPException(status_code=403, detail="Sem permissão para acessar este agente")
    
    # Verificar se o dispositivo existe e pertence ao tenant
    # (Implementar verificação do dispositivo)
    
    # Atribuir/desvinculação
    if active:
        result = agent_service.assign_agent_to_device(agent_id, device_id)
    else:
        result = agent_service.unassign_agent_from_device(agent_id, device_id)
    
    if not result:
        raise HTTPException(status_code=400, detail="Falha ao atualizar associação do dispositivo")
    
    return {"success": True, "message": "Associação de dispositivo atualizada com sucesso"}