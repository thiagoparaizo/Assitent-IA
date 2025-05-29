from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_agent_service, get_current_active_user, get_tenant_id, get_whatsapp_service
from app.schemas import whatsapp as schemas
from app.db.models.user import User
from app.services.agent import AgentService
from app.services.whatsapp import WhatsAppService

router = APIRouter()

import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("app.api.endpoints.whatsapp")

@router.get("/devices/", response_model=List[schemas.Device])
async def get_devices(
    tenant_id: int,
    current_user: User = Depends(get_current_active_user),
    whatsapp_service: WhatsAppService = Depends(get_whatsapp_service),
):
    """
    Obtém a lista de dispositivos de um tenant
    """
    if not current_user.is_superuser and current_user.tenant_id != int(tenant_id):
        raise HTTPException(status_code=403, detail="Sem permissão para acessar este tenant")
    
    return await whatsapp_service.get_devices(tenant_id)


@router.get("/devices/{device_id}", response_model=schemas.Device)
async def get_device(
    device_id: int,
    current_user: User = Depends(get_current_active_user),
    whatsapp_service: WhatsAppService = Depends(get_whatsapp_service),
):
    """
    Obtém informações de um dispositivo específico
    """
    device = await whatsapp_service.get_device(device_id)
    
    if not current_user.is_superuser and current_user.tenant_id != device["tenant_id"]:
        raise HTTPException(status_code=403, detail="Sem permissão para acessar este dispositivo")
    
    return device


@router.post("/devices/", response_model=schemas.Device)
async def create_device(
    device: schemas.DeviceCreate,
    current_user: User = Depends(get_current_active_user),
    whatsapp_service: WhatsAppService = Depends(get_whatsapp_service),
):
    """
    Cria um novo dispositivo
    """
    if not current_user.is_superuser and current_user.tenant_id != device.tenant_id:
        raise HTTPException(status_code=403, detail="Sem permissão para criar dispositivo para este tenant")
    
    return await whatsapp_service.create_device(
        tenant_id=device.tenant_id,
        name=device.name,
        description=device.description,
        phone_number=device.phone_number,
    )


@router.put("/devices/{device_id}/status", response_model=dict)
async def update_device_status(
    device_id: int,
    status: schemas.DeviceStatusUpdate,
    current_user: User = Depends(get_current_active_user),
    whatsapp_service: WhatsAppService = Depends(get_whatsapp_service),
):
    """
    Atualiza o status de um dispositivo
    """
    # Verificar permissão - deve buscar o dispositivo antes para verificar o tenant_id
    device = await whatsapp_service.get_device(device_id)
    
    if not current_user.is_superuser and current_user.tenant_id != device["tenant_id"]:
        raise HTTPException(status_code=403, detail="Sem permissão para atualizar este dispositivo")
    
    return await whatsapp_service.update_device_status(device_id, status.status)


@router.get("/devices/{device_id}/status", response_model=schemas.DeviceStatus)
async def get_device_status(
    device_id: int,
    current_user: User = Depends(get_current_active_user),
    whatsapp_service: WhatsAppService = Depends(get_whatsapp_service),
):
    """
    Obtém o status atual de um dispositivo
    """
    # Verificar permissão - deve buscar o dispositivo antes para verificar o tenant_id
    device = await whatsapp_service.get_device(device_id)
    
    if not current_user.is_superuser and current_user.tenant_id != device["tenant_id"]:
        raise HTTPException(status_code=403, detail="Sem permissão para visualizar o status deste dispositivo")
    
    return await whatsapp_service.get_device_status(device_id)


@router.get("/devices/{device_id}/qrcode", response_model=dict)
async def get_qr_code(
    device_id: int,
    current_user: User = Depends(get_current_active_user),
    whatsapp_service: WhatsAppService = Depends(get_whatsapp_service),
):
    """
    Obtém o QR code para vincular um dispositivo
    """
    # Verificar permissão - deve buscar o dispositivo antes para verificar o tenant_id
    device = await whatsapp_service.get_device(device_id)
    
    if not current_user.is_superuser and current_user.tenant_id != device["tenant_id"]:
        raise HTTPException(status_code=403, detail="Sem permissão para obter QR code deste dispositivo")
    
    return await whatsapp_service.get_qr_code(device_id)


@router.post("/devices/{device_id}/send", response_model=dict)
async def send_message(
    device_id: int,
    message: schemas.MessageSend,
    current_user: User = Depends(get_current_active_user),
    whatsapp_service: WhatsAppService = Depends(get_whatsapp_service),
):
    """
    Envia uma mensagem de texto
    """
    # Verificar permissão - deve buscar o dispositivo antes para verificar o tenant_id
    device = await whatsapp_service.get_device(device_id)
    
    if not current_user.is_superuser and current_user.tenant_id != device["tenant_id"]:
        raise HTTPException(status_code=403, detail="Sem permissão para enviar mensagens por este dispositivo")
    
    return await whatsapp_service.send_message(
        device_id=device_id,
        to=message.to,
        message=message.content,
    )


@router.get("/devices/{device_id}/contacts", response_model=dict)
async def get_contacts(
    device_id: int,
    current_user: User = Depends(get_current_active_user),
    whatsapp_service: WhatsAppService = Depends(get_whatsapp_service),
):
    """
    Obtém a lista de contatos
    """
    # Verificar permissão - deve buscar o dispositivo antes para verificar o tenant_id
    device = await whatsapp_service.get_device(device_id)
    
    if not current_user.is_superuser and current_user.tenant_id != device["tenant_id"]:
        raise HTTPException(status_code=403, detail="Sem permissão para acessar os contatos deste dispositivo")
    
    return await whatsapp_service.get_contacts(device_id)


@router.get("/devices/{device_id}/groups", response_model=List[dict])
async def get_groups(
    device_id: int,
    current_user: User = Depends(get_current_active_user),
    whatsapp_service: WhatsAppService = Depends(get_whatsapp_service),
):
    """
    Obtém a lista de grupos
    """
    # Verificar permissão - deve buscar o dispositivo antes para verificar o tenant_id
    device = await whatsapp_service.get_device(device_id)
    
    if not current_user.is_superuser and current_user.tenant_id != device["tenant_id"]:
        raise HTTPException(status_code=403, detail="Sem permissão para acessar os grupos deste dispositivo")
    
    return await whatsapp_service.get_groups(device_id)


@router.get("/devices/{device_id}/contact/{contact_id}/messages", response_model=List[schemas.Message])
async def get_contact_messages(
    device_id: int,
    contact_id: str,
    filter: str = Query("day", description="Filtro de tempo: new, day, week, month"),
    current_user: User = Depends(get_current_active_user),
    whatsapp_service: WhatsAppService = Depends(get_whatsapp_service),
):
    """
    Obtém mensagens de um contato específico
    """
    # Verificar permissão - deve buscar o dispositivo antes para verificar o tenant_id
    device = await whatsapp_service.get_device(device_id)
    
    if not current_user.is_superuser and current_user.tenant_id != device["tenant_id"]:
        raise HTTPException(status_code=403, detail="Sem permissão para acessar as mensagens deste dispositivo")
    
    # Obter mensagens do serviço, que retorna no formato Go
    go_messages = await whatsapp_service.get_contact_messages(device_id, contact_id, filter)
    
    # Tratamento para quando não há mensagens (retorno null do serviço Go)
    if go_messages is None:
        return []
    
    # Transformar as mensagens para o formato Python
    transformed_messages = []
    for msg in go_messages:
        transformed = {
            "id": msg.get("ID"),
            "device_id": msg.get("DeviceID"),
            "jid": msg.get("JID"),
            "message_id": msg.get("MessageID"),
            "sender": msg.get("Sender"),
            "is_from_me": msg.get("IsFromMe", False),
            "is_group": msg.get("IsGroup", False),
            "content": msg.get("Content", ""),
            "media_url": msg.get("MediaURL", ""),
            "media_type": msg.get("MediaType", ""),
            "timestamp": msg.get("Timestamp"),
            "received_at": msg.get("ReceivedAt")
        }
        transformed_messages.append(transformed)
    
    return transformed_messages


@router.get("/devices/{device_id}/group/{group_id}/messages", response_model=List[schemas.Message])
async def get_group_messages(
    device_id: int,
    group_id: str,
    filter: str = Query("day", description="Filtro de tempo: new, day, week, month"),
    current_user: User = Depends(get_current_active_user),
    whatsapp_service: WhatsAppService = Depends(get_whatsapp_service),
):
    """
    Obtém mensagens de um grupo específico
    """
    # Verificar permissão - deve buscar o dispositivo antes para verificar o tenant_id
    device = await whatsapp_service.get_device(device_id)
    
    if not current_user.is_superuser and current_user.tenant_id != device["tenant_id"]:
        raise HTTPException(status_code=403, detail="Sem permissão para acessar as mensagens deste dispositivo")
    
    # Obter mensagens do serviço, que retorna no formato Go
    go_messages = await whatsapp_service.get_group_messages(device_id, group_id, filter)
    
    # Tratamento para quando não há mensagens (retorno null do serviço Go)
    if go_messages is None:
        return []
    
    # Transformar as mensagens para o formato Python
    transformed_messages = []
    for msg in go_messages:
        transformed = {
            "id": msg.get("ID"),
            "device_id": msg.get("DeviceID"),
            "jid": msg.get("JID"),
            "message_id": msg.get("MessageID"),
            "sender": msg.get("Sender"),
            "is_from_me": msg.get("IsFromMe", False),
            "is_group": msg.get("IsGroup", False),
            "content": msg.get("Content", ""),
            "media_url": msg.get("MediaURL", ""),
            "media_type": msg.get("MediaType", ""),
            "timestamp": msg.get("Timestamp"),
            "received_at": msg.get("ReceivedAt")
        }
        transformed_messages.append(transformed)
    
    return transformed_messages


@router.post("/devices/{device_id}/group/{group_id}/send", response_model=dict)
async def send_group_message(
    device_id: int,
    group_id: str,
    message: schemas.GroupMessageSend,
    current_user: User = Depends(get_current_active_user),
    whatsapp_service: WhatsAppService = Depends(get_whatsapp_service),
):
    """
    Envia uma mensagem para um grupo
    """
    # Verificar permissão - deve buscar o dispositivo antes para verificar o tenant_id
    device = await whatsapp_service.get_device(device_id)
    
    if not current_user.is_superuser and current_user.tenant_id != device["tenant_id"]:
        raise HTTPException(status_code=403, detail="Sem permissão para enviar mensagens por este dispositivo")
    
    return await whatsapp_service.send_group_message(
        device_id=device_id,
        group_id=group_id,
        message=message.message,
    )


@router.get("/devices/{device_id}/tracked", response_model=List[schemas.TrackedEntity])
async def get_tracked_entities(
    device_id: int,
    current_user: User = Depends(get_current_active_user),
    whatsapp_service: WhatsAppService = Depends(get_whatsapp_service),
):
    """
    Obtém a lista de entidades rastreadas
    """
    # Verificar permissão - deve buscar o dispositivo antes para verificar o tenant_id
    device = await whatsapp_service.get_device(device_id)
    
    if not current_user.is_superuser and current_user.tenant_id != device["tenant_id"]:
        raise HTTPException(status_code=403, detail="Sem permissão para acessar este dispositivo")
    
    orig_entities = await whatsapp_service.get_tracked_entities(device_id)
    
    # Transformar as entidades para corresponder ao modelo TrackedEntity
    transformed_entities = []
    for entity in orig_entities:
        transformed = {
            "id": entity.get("ID"),
            "device_id": entity.get("DeviceID"),
            "jid": entity.get("JID"),
            "is_tracked": entity.get("IsTracked", True),
            "track_media": entity.get("TrackMedia", True),
            "allowed_media_types": entity.get("AllowedMediaTypes", []),
            "created_at": entity.get("CreatedAt"),
            "updated_at": entity.get("UpdatedAt")
        }
        transformed_entities.append(transformed)
    
    return transformed_entities

# Adicionar ao arquivo app/api/endpoints/whatsapp.py

@router.post("/devices/{device_id}/tracked", response_model=schemas.TrackedEntity)
async def set_tracked_entity(
    device_id: int,
    entity_data: schemas.TrackedEntityCreate,
    current_user: User = Depends(get_current_active_user),
    whatsapp_service: WhatsAppService = Depends(get_whatsapp_service),
):
    """
    Configura uma entidade para ser rastreada
    """
    # Verificar permissão - deve buscar o dispositivo antes para verificar o tenant_id
    device = await whatsapp_service.get_device(device_id)
    
    if not current_user.is_superuser and current_user.tenant_id != device["tenant_id"]:
        raise HTTPException(status_code=403, detail="Sem permissão para configurar rastreamento neste dispositivo")
    
    # Transformar os dados para o formato esperado pelo serviço Go
    go_data = {
        "jid": entity_data.jid,
        "is_tracked": entity_data.is_tracked,
        "track_media": entity_data.track_media,
        "allowed_media_types": entity_data.allowed_media_types
    }
    
    # Chamar o serviço
    result = await whatsapp_service.set_tracked_entity(
        device_id=device_id,
        jid=entity_data.jid,
        is_tracked=entity_data.is_tracked,
        track_media=entity_data.track_media,
        allowed_media_types=entity_data.allowed_media_types
    )
    
    # Transformar o resultado de volta para o formato esperado pelo schema
    transformed = {
        "id": result.get("ID"),
        "device_id": result.get("DeviceID"),
        "jid": result.get("JID"),
        "is_tracked": result.get("IsTracked", True),
        "track_media": result.get("TrackMedia", True),
        "allowed_media_types": result.get("AllowedMediaTypes", []),
        "created_at": result.get("CreatedAt"),
        "updated_at": result.get("UpdatedAt")
    }
    
    return transformed

@router.delete("/devices/{device_id}/tracked/{jid}")
async def delete_tracked_entity(
    device_id: int,
    jid: str,
    current_user: User = Depends(get_current_active_user),
    whatsapp_service: WhatsAppService = Depends(get_whatsapp_service),
):
    """
    Remove uma entidade rastreada
    """
    # Verificar permissão - deve buscar o dispositivo antes para verificar o tenant_id
    device = await whatsapp_service.get_device(device_id)
    
    if not current_user.is_superuser and current_user.tenant_id != device["tenant_id"]:
        raise HTTPException(status_code=403, detail="Sem permissão para remover rastreamento neste dispositivo")
    
    result = await whatsapp_service.delete_tracked_entity(device_id, jid)
    
    # Transformar o resultado, se necessário
    transformed_result = {}
    if isinstance(result, dict):
        if "status" in result:
            transformed_result["status"] = result.get("status")
        if "message" in result:
            transformed_result["message"] = result.get("message")
    else:
        transformed_result = {"status": "success", "message": "Entidade removida do rastreamento com sucesso"}
    
    return transformed_result

@router.post("/devices/{device_id}/assign/{agent_id}")
async def assign_agent_to_device(
    device_id: int,
    agent_id: str,
    tenant_id: str = Depends(get_tenant_id),
    agent_service: AgentService = Depends(get_agent_service),
    current_user: User = Depends(get_current_active_user),
):
    """Atribui um agente a um dispositivo específico."""
    # Verificar permissões
    # Verificar se o dispositivo pertence ao tenant
    # Atribuir agente
    result = await agent_service.assign_agent_to_device(agent_id, device_id)
    if not result:
        raise HTTPException(status_code=400, detail="Falha ao atribuir agente ao dispositivo")
    
    return {"status": "success", "message": "Agente atribuído com sucesso"}

@router.get("/devices/{device_id}/contact/{contact_id}/messages")
async def get_contact_messages(
    device_id: int,
    contact_id: str,
    filter: str = Query("day", description="Filtro de tempo: new, day, week, month"),
    current_user: User = Depends(get_current_active_user),
    whatsapp_service: WhatsAppService = Depends(get_whatsapp_service),
):
    """
    Obtém mensagens de um contato específico
    """
    # Verificar permissão - deve buscar o dispositivo antes para verificar o tenant_id
    device = await whatsapp_service.get_device(device_id)
    
    if not current_user.is_superuser and current_user.tenant_id != device["tenant_id"]:
        raise HTTPException(status_code=403, detail="Sem permissão para acessar as mensagens deste dispositivo")
    
    return await whatsapp_service.get_contact_messages(device_id, contact_id, filter)


from typing import Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import ALGORITHM
from app.db.session import SessionLocal
from app.db.models.user import User
from app.schemas.token import TokenPayload
from app.services.whatsapp import WhatsAppService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")


def get_db() -> Generator:
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()


# def get_current_user(
#     db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)
# ) -> User:
#     print("get_current_user >>")
#     try:
#         payload = jwt.decode(
#             token, settings.SECRET_KEY, algorithms=[ALGORITHM]
#         )
#         token_data = TokenPayload(**payload)
#     except (jwt.JWTError, ValidationError):
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail="Não foi possível validar as credenciais",
#         )
#     user = db.query(User).filter(User.id == token_data.sub).first()
#     if not user:
#         raise HTTPException(status_code=404, detail="Usuário não encontrado")
#     return user


# def get_current_active_user(
#     current_user: User = Depends(get_current_user),
# ) -> User:
#     if not current_user.is_active:
#         raise HTTPException(status_code=400, detail="Usuário inativo")
#     return current_user


# def get_current_active_superuser(
#     current_user: User = Depends(get_current_user),
# ) -> User:
#     if not current_user.is_superuser:
#         raise HTTPException(
#             status_code=400, detail="O usuário não tem privilégios suficientes"
#         )
#     return current_user


def get_whatsapp_service() -> WhatsAppService:
    return WhatsAppService()