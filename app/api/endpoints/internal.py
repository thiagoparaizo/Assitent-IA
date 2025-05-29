import asyncio
import json
import os
import time
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_whatsapp_service
from app.db.models.tenant import Tenant
from app.db.models.user import User
from app.services.whatsapp import WhatsAppService
import logging

router = APIRouter()

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("app.api.endpoints.internal")

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
    db: Session = Depends(get_db),
    whatsapp_service: WhatsAppService = Depends(get_whatsapp_service),
):
    """
    Recebe eventos do WhatsApp Server e processa baseado na configuração de webhooks.
    Este endpoint é para uso interno do WhatsApp Server.
    """
    # Importar o processamento de webhook da implementação existente
    from app.api.endpoints.webhook import process_whatsapp_message
    
    
    logger.debug(f"process_webhook_event: Webhook received: {event}")
    
    # Verificar se é uma mensagem (ignorar outros tipos de eventos)
    if event.get("event_type") != "*events.Message":
        # Para outros tipos de eventos, processar imediatamente
        logger.debug(f"process_webhook_event: Non-message event type: {event.get('event_type')}, processing immediately")
        await process_whatsapp_message(event, whatsapp_service, db)
        return {"status": "processed"}
    
    # Verificar se há dados de áudio processado
    audio_data = event.get("audio_data")
    has_audio = audio_data is not None and audio_data.get("base64")
    
    if has_audio:
        logger.info(f"Audio message received for processing: {event.get('device_id')}")
        # Para mensagens de áudio, processar imediatamente (não enfileirar)
        await process_whatsapp_message(event, whatsapp_service, db)
        return {"status": "processed_audio"}
    
    
    # Extrair informações relevantes
    tenant_id = event.get("tenant_id")
    device_id = event.get("device_id")
    
    # Informações do chat/contato
    event_info = event.get("event", {}).get("Info", {})
    chat_jid = event_info.get("Chat")
    sender = event_info.get("Sender", {})
    if 'User' in sender:
        sender = sender['User']
        
    is_from_me = event_info.get("IsFromMe", False)
    is_group = event_info.get("IsGroup", False)
    contact_id = chat_jid if is_group else sender
    
    # Para mensagens enviadas pelo próprio dispositivo, processar imediatamente
    if is_from_me:
        logger.debug(f"process_webhook_event: Message from device {device_id}, processing immediately")
        await process_whatsapp_message(event, whatsapp_service, db)
        return {"status": "processed"}
    
    # Para grupos, poderia ter uma configuração diferente (opcional)
    if is_group:
        # Opção 1: Processar grupos imediatamente (evitar conflito em conversas de grupo)
        logger.debug(f"Group message {chat_jid}, processing immediately")
        await process_whatsapp_message(event, whatsapp_service, db)
        return {"status": "processed"}
        
        # Opção 2: Usar uma configuração de delay menor para grupos (por exemplo, 5 segundos)
        # group_delay = 5  # segundos
        
        # Optando por usar o mesmo delay para todos (pode ser configurável por tenant)
        pass
    
    # Se chegarmos aqui, é uma mensagem normal para enfileirar
    try:
        # Obter cliente Redis
        import redis.asyncio as redis
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        redis_client = redis.from_url(redis_url)
        
        # Key para a fila de mensagens deste chat
        queue_key = f"whatsapp_message_queue:{tenant_id}:{chat_jid}"
        
        # Key para o lock de processamento
        processing_key = f"whatsapp_processing_scheduled:{tenant_id}:{chat_jid}"
        
        # Verificar o conteúdo da mensagem
        event_message = event.get("event", {}).get("Message", {})
        message_content = event_message.get("Conversation")
        
        if not message_content:
            # Tentar extrair de outros tipos de mensagem
            if ext_text := event_message.get("ExtendedTextMessage", {}):
                message_content = ext_text.get("Text", "")
        
        # Verificar se há conteúdo de texto válido
        if not message_content:
            # Para mensagens sem texto (mídia, etc.), processar imediatamente
            logger.debug(f"Message without text content from {chat_jid}, processing immediately")
            await process_whatsapp_message(event, whatsapp_service, db)
            return {"status": "processed_immediate"}
        
        # Obter timestamp atual
        current_time = time.time()
        
        # Criar dados da mensagem com timestamp
        message_data = {
            "event": event,
            "timestamp": current_time,
            "content": message_content
        }
        
        # Adicionar à fila no Redis
        await redis_client.rpush(queue_key, json.dumps(message_data))
        
        # Atualizar TTL da fila (para garantir limpeza em caso de falha)
        await redis_client.expire(queue_key, 300)  # 5 minutos TTL
        
        # Verificar se já há processamento agendado
        already_scheduled = await redis_client.get(processing_key)
        
        if not already_scheduled:
            # Definir flag para evitar agendamentos múltiplos
            await redis_client.set(processing_key, "1", ex=20)  # 20 segundos TTL
            
            # Configuração do tempo de espera (poderia ser por tenant/agente)
            delay_seconds = 15  # 15 segundos de espera
            
            # Agendar processamento após o delay
            asyncio.create_task(
                process_message_queue(
                    tenant_id=tenant_id,
                    chat_jid=chat_jid,
                    delay_seconds=delay_seconds,
                    whatsapp_service=whatsapp_service,
                    db=db
                )
            )
            
            logger.info(f"Scheduled message queue processing for {chat_jid} in {delay_seconds} seconds")
        
        return {"status": "queued"}
        
    except Exception as e:
        logger.error(f"Error queueing message: {e}")
        logger.exception(e)
        
        # Em caso de erro no mecanismo de fila, processar normalmente
        await process_whatsapp_message(event, whatsapp_service, db)
        return {"status": "processed_fallback"}


async def process_message_queue(
    tenant_id: str,
    chat_jid: str,
    delay_seconds: int,
    whatsapp_service: WhatsAppService,
    db: Session
):
    """
    Processa a fila de mensagens após um período de espera.
    Se novas mensagens chegarem durante o período, reinicia a contagem.
    """
    try:
        # Esperar pelo delay especificado
        await asyncio.sleep(delay_seconds)
        
        # Obter cliente Redis
        import redis.asyncio as redis
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        redis_client = redis.from_url(redis_url)
        
        # Keys para Redis
        queue_key = f"whatsapp_message_queue:{tenant_id}:{chat_jid}"
        processing_key = f"whatsapp_processing_scheduled:{tenant_id}:{chat_jid}"
        
        # Obter todas as mensagens da fila
        all_messages_json = await redis_client.lrange(queue_key, 0, -1)
        
        if not all_messages_json:
            logger.warning(f"No messages found in queue for {chat_jid}")
            await redis_client.delete(processing_key)
            return
        
        # Converter de JSON para dicionários
        all_messages = [json.loads(msg) for msg in all_messages_json]
        
        # Verificar se alguma mensagem é muito recente
        current_time = time.time()
        newest_message_time = max(msg["timestamp"] for msg in all_messages)
        time_since_last = current_time - newest_message_time
        
        if time_since_last < delay_seconds:
            # Se chegou mensagem recente, reagendar processamento
            remaining_delay = delay_seconds - time_since_last
            
            logger.info(f"Recent message detected for {chat_jid}, rescheduling in {remaining_delay:.1f}s")
            
            # Renovar o TTL da flag de processamento
            await redis_client.expire(processing_key, int(remaining_delay) + 5)
            
            # Criar nova tarefa com o delay restante
            asyncio.create_task(
                process_message_queue(
                    tenant_id=tenant_id,
                    chat_jid=chat_jid,
                    delay_seconds=int(remaining_delay) + 1,
                    whatsapp_service=whatsapp_service,
                    db=db
                )
            )
            return
        
        # Se chegamos aqui, é hora de processar as mensagens
        logger.info(f"Processing {len(all_messages)} queued messages for {chat_jid}")
        
        # Ordenar mensagens por timestamp
        sorted_messages = sorted(all_messages, key=lambda x: x["timestamp"])
        
        # Combinar conteúdo das mensagens
        combined_content = ""
        for i, msg_data in enumerate(sorted_messages):
            content = msg_data["content"]
            if content:
                if i > 0:  # Adicionar quebra de linha entre mensagens
                    combined_content += "\n"
                combined_content += content
        
        if not combined_content:
            logger.warning(f"No valid message content found in queue for {chat_jid}")
            await redis_client.delete(queue_key)
            await redis_client.delete(processing_key)
            return
        
        # Pegar o evento mais recente para processar
        latest_event = sorted_messages[-1]["event"]
        
        # Substituir o conteúdo no evento mais recente
        message_obj = latest_event.get("event", {}).get("Message", {})
        if "Conversation" in message_obj:
            message_obj["Conversation"] = combined_content
        elif "ExtendedTextMessage" in message_obj:
            message_obj["ExtendedTextMessage"]["Text"] = combined_content
        
        # Processar o evento combinado
        from app.api.endpoints.webhook import process_whatsapp_message
        await process_whatsapp_message(latest_event, whatsapp_service, db)
        
        # Limpar a fila e a flag de processamento
        await redis_client.delete(queue_key)
        await redis_client.delete(processing_key)
        
        logger.info(f"Successfully processed {len(all_messages)} combined messages for {chat_jid}")
        
    except Exception as e:
        logger.error(f"Error processing message queue for {chat_jid}: {e}")
        logger.exception(e)
        
        # Tentar limpar as chaves em caso de erro
        try:
            import redis.asyncio as redis
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            redis_client = redis.from_url(redis_url)
            
            queue_key = f"whatsapp_message_queue:{tenant_id}:{chat_jid}"
            processing_key = f"whatsapp_processing_scheduled:{tenant_id}:{chat_jid}"
            
            await redis_client.delete(processing_key)
        except:
            pass

router.get("/init_db")
def init_db():
    from app.db.init_db import init_db
    init_db()
    