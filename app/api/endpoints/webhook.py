import hashlib
import hmac
import logging
import asyncio
import os
import re
from typing import Dict, Any, Optional, List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Path, Query
from sqlalchemy.orm import Session
import uuid
import json
import time
from datetime import datetime

from app.api.deps import get_db, get_llm_service, get_tenant_id, get_whatsapp_service
from app.core.redis import get_redis
from app.schemas.agent import AgentType
from app.services.agent import AgentService
from app.services.config import load_system_config
#from app.services.llm import LLMService
from app.services.orchestrator import AgentOrchestrator
from app.services.rag_faiss import RAGServiceFAISS
from app.services.token_counter import TokenCounterService
from app.services.whatsapp import WhatsAppService
from app.db.models.webhook import Webhook, WebhookLog
from app.db.models.agent import Agent
from app.db.models.conversation import ConversationState
from app.schemas.webhook import WebhookCreate, WebhookResponse, WebhookLogResponse
from app.api.utils.webhook_processor import process_whatsapp_message, send_webhook_request

from app.utils.audio_helpers import (
    get_audio_error_response,
    get_error_response_generic,
    llm_supports_audio, 
    extract_audio_info, 
    validate_audio_data,
    get_audio_not_supported_response,
    log_audio_processing
)

router = APIRouter()

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("app.api.endpoints.webhook")


@router.post("")
async def whatsapp_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    whatsapp_service: WhatsAppService = Depends(get_whatsapp_service),
    db: Session = Depends(get_db),
):
    """
    Webhook to receive events from the WhatsApp service
    """
    try:
        data = await request.json()
        logger.info(f"Webhook received: {data}")
        
        # Check if it's a message
        if data.get("event_type") == "*events.Message":
            # Process message in background
            background_tasks.add_task(
                process_whatsapp_message,
                data,
                whatsapp_service,
                db
            )
        
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
async def get_webhooks(
    tenant_id: str = Depends(get_tenant_id),
    db: Session = Depends(get_db),
):
    """
    List webhooks configured for a tenant
    """
    try:
        # Query webhooks for this tenant
        webhooks = db.query(Webhook).filter(Webhook.tenant_id == tenant_id).all()
        
        # Convert to response format
        result = []
        for webhook in webhooks:
            result.append(WebhookResponse(
                id=webhook.id,
                url=webhook.url,
                secret=webhook.secret if webhook.secret else None,
                events=json.loads(webhook.events) if webhook.events else [],
                device_ids=json.loads(webhook.device_ids) if webhook.device_ids else [],
                tenant_id=webhook.tenant_id,
                enabled=webhook.enabled,
                created_at=webhook.created_at,
                updated_at=webhook.updated_at
            ))
        
        return result
    except Exception as e:
        logger.error(f"Error getting webhooks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/create", response_model=WebhookResponse)
async def create_webhook(
    webhook: WebhookCreate,
    tenant_id: str = Depends(get_tenant_id),
    db: Session = Depends(get_db),
):
    """
    Create a new webhook
    """
    try:
        # Converter a URL para string
        url_str = str(webhook.url)
        
        # Create webhook
        new_webhook = Webhook(
            id=str(uuid.uuid4()),
            url=url_str,  # Usar a string aqui
            secret=webhook.secret,
            events=json.dumps(webhook.events) if webhook.events else None,
            device_ids=json.dumps(webhook.device_ids) if webhook.device_ids else None,
            tenant_id=tenant_id,
            enabled=webhook.enabled
        )
        
        # Add to database
        db.add(new_webhook)
        db.commit()
        db.refresh(new_webhook)
        
        # Convert to response model
        return WebhookResponse(
            id=new_webhook.id,
            url=webhook.url,  # Aqui podemos usar o objeto original
            secret=new_webhook.secret,
            events=webhook.events,
            device_ids=webhook.device_ids,
            tenant_id=new_webhook.tenant_id,
            enabled=new_webhook.enabled,
            created_at=new_webhook.created_at,
            updated_at=new_webhook.updated_at
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{webhook_id}", response_model=WebhookResponse)
async def get_webhook(
    webhook_id: str = Path(...),
    tenant_id: str = Depends(get_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Get a specific webhook
    """
    webhook = db.query(Webhook).filter(
        Webhook.id == webhook_id,
        Webhook.tenant_id == tenant_id
    ).first()
    
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    return WebhookResponse(
        id=webhook.id,
        url=webhook.url,
        secret=webhook.secret,
        events=json.loads(webhook.events) if webhook.events else [],
        device_ids=json.loads(webhook.device_ids) if webhook.device_ids else [],
        tenant_id=webhook.tenant_id,
        enabled=webhook.enabled,
        created_at=webhook.created_at,
        updated_at=webhook.updated_at
    )


@router.delete("/{webhook_id}")
async def delete_webhook(
    webhook_id: str = Path(...),
    tenant_id: str = Depends(get_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Delete a webhook
    """
    webhook = db.query(Webhook).filter(
        Webhook.id == webhook_id,
        Webhook.tenant_id == tenant_id
    ).first()
    
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    # Delete webhook
    db.delete(webhook)
    db.commit()
    
    return {"status": "success", "message": "Webhook deleted successfully"}


@router.post("/{webhook_id}/test")
async def test_webhook(
    background_tasks: BackgroundTasks,
    webhook_id: str = Path(...),
    tenant_id: str = Depends(get_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Test a webhook by sending a dummy event
    """
    webhook = db.query(Webhook).filter(
        Webhook.id == webhook_id,
        Webhook.tenant_id == tenant_id
    ).first()
    
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    # Create test event
    test_event = {
        "tenant_id": tenant_id,
        "device_id": 0,
        "event_type": "test_event",
        "timestamp": datetime.now().isoformat(),
        "event": {
            "message": "This is a test event"
        }
    }
    
    # Send webhook in background
    background_tasks.add_task(
        send_webhook_request,
        webhook,
        test_event,
        db
    )
    
    return {"status": "success", "message": "Test webhook dispatched"}


@router.get("/{webhook_id}/logs", response_model=List[WebhookLogResponse])
async def get_webhook_logs(
    webhook_id: str = Path(...),
    limit: int = Query(20, ge=1, le=100),
    tenant_id: str = Depends(get_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Get webhook delivery logs
    """
    # Check if webhook exists and belongs to tenant
    webhook = db.query(Webhook).filter(
        Webhook.id == webhook_id,
        Webhook.tenant_id == tenant_id
    ).first()
    
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    # Get logs
    logs = db.query(WebhookLog).filter(
        WebhookLog.webhook_id == webhook_id
    ).order_by(WebhookLog.created_at.desc()).limit(limit).all()
    
    # Convert to response format
    result = []
    for log in logs:
        result.append(WebhookLogResponse(
            id=log.id,
            webhook_id=log.webhook_id,
            status=log.status,
            event_type=log.event_type,
            attempt_count=log.attempt_count,
            response_code=log.response_code,
            response_body=log.response_body,
            error_message=log.error_message,
            payload=log.payload,
            created_at=log.created_at
        ))
    
    return result

# função principal que processa as mensagens recebidas do WhatsApp
async def process_whatsapp_message(data: Dict[str, Any], whatsapp_service: WhatsAppService, db: Session):
    """
    Processa mensagens recebidas do WhatsApp usando o sistema de agentes inteligentes, com suporte a áudio usando funções auxiliares.
    """
    try:
        # Extrair informações da mensagem
        device_id = data.get("device_id")
        tenant_id = data.get("tenant_id")
        
        # Extrair e validar dados de áudio
        audio_info = extract_audio_info(data)
        has_valid_audio = audio_info and validate_audio_data(audio_info)
        
        if audio_info and not has_valid_audio:
            logger.warning(f"Invalid audio data received from device {device_id}")
            # Pode optar por continuar sem áudio ou retornar erro
            audio_info = None
        
        sender = data.get("event", {}).get("Info", {}).get("Sender", {})
        if 'User' in sender:
            sender = sender['User']
        chat_jid = data.get("event", {}).get("Info", {}).get("Chat")
        
        # # Verificar se há dados de áudio
        # audio_data = data.get("audio_data")
        # has_audio = audio_data is not None and audio_data.get("base64")
        
        # O contact_id pode ser o ID do remetente ou do chat, dependendo se é grupo ou não
        is_group = data.get("event", {}).get("Info", {}).get("IsGroup", False)
        contact_id = chat_jid if is_group else sender
        
        event = data.get("event", {})
        
        # Lidar com mensagens enviadas pelo próprio dispositivo para controle do agente
        if event.get("Info", {}).get("IsFromMe"):
            # Extrair conteúdo da mensagem
            message_content = event.get("Message", {}).get("Conversation")
            
            if not message_content:
                # Tentar extrair de outros tipos de mensagem
                if ext_text := event.get("Message", {}).get("ExtendedTextMessage", {}):
                    message_content = ext_text.get("Text", "")
            
            # Verificar comandos de controle
            if message_content:
                message_content = message_content.strip()
                
                # Inicializar Redis
                redis_client = await get_redis()
                
                # Chave para armazenar o estado do agente para esta conversa
                agent_control_key = f"agent_control:{tenant_id}:{chat_jid}"
                
                if message_content == "@stop" or message_content == "@parar" or message_content == "@desativar":
                    # Desativar o agente para esta conversa
                    await redis_client.set(agent_control_key, "disabled")
                    await redis_client.expire(agent_control_key, 60 * 60 * 24 * 7)  # 7 dias
                    
                    # Log e resposta de confirmação
                    logger.info(f"Agente desativado para conversa com {chat_jid}")
                    await whatsapp_service.send_message(
                        device_id=device_id,
                        to=chat_jid,
                        message="⏸️"
                    )
                    return
                
                elif message_content == "@ok" or message_content == "@ativar" or message_content == "@start" or message_content == "@reativar" or message_content == "@restart" or message_content == "@reiniciar" or message_content == "@eu":
                    # Reativar o agente para esta conversa
                    await redis_client.delete(agent_control_key)
                    
                    # Log e resposta de confirmação
                    logger.info(f"Agente reativado para conversa com {chat_jid}, removendo a chave {agent_control_key}")
                    print(f"Agente reativado para conversa com {chat_jid}, removendo a chave {agent_control_key}")
                    await whatsapp_service.send_message(
                        device_id=device_id,
                        to=chat_jid,
                        message="✅"
                    )
                    return
            
            # Para outras mensagens do próprio dispositivo, ignorar normalmente
            logger.warning(f"Mensagem enviada pelo próprio dispositivo {device_id} do tenant {tenant_id}. Será ignorada")
            return
        
        message_content = event.get("Message", {}).get("Conversation")
        
        if not message_content:
            # Tentar extrair de outros tipos de mensagem
            if ext_text := event.get("Message", {}).get("ExtendedTextMessage", {}):
                message_content = ext_text.get("Text", "")
        
        if not message_content and not has_valid_audio:
            # Ignorar mensagens sem conteúdo de texto
            logger.warning(f"Mensagem sem conteudo de texto do dispositivo {device_id} do tenant {tenant_id}. Sera ignorada")
            print(f"Mensagem sem conteudo de texto do dispositivo {device_id} do tenant {tenant_id}. Sera ignorada")
            return
        
        # Inicializar cliente Redis
        redis_client = await get_redis()
        
        agent_control_key = f"agent_control:{tenant_id}:{chat_jid}"
        agent_status = await redis_client.get(agent_control_key)
        
        if agent_status and agent_status.decode("utf-8") == "disabled":
            logger.info(f"Mensagem ignorada: agente desativado para conversa com {chat_jid}")
            return
        
        # Converter para objeto Agent
        agent_service = AgentService(db, None) # Instanciar sem Redis para conversão
        agent, should_response = await agent_service.get_agent_for_contact(device_id, tenant_id, contact_id)
        
        if agent:
            logger.info(f"Agent (get_agent_for_contact): should_response: {should_response} | Agent: {agent.id} ({agent.name} - Tenant: {agent.tenant_id} | Device Id: {device_id} | Contact Id: {contact_id}")
            print(f"Agent (get_agent_for_contact): should_response: {should_response} | Agent: {agent.id} ({agent.name} - Tenant: {agent.tenant_id} | Device Id: {device_id} | Contact Id: {contact_id}")
        else:
            logger.info(f"Agent (get_agent_for_contact): should_response: {should_response} | Agent: None | Device Id: {device_id} | Contact Id: {contact_id}")
            print(f"Agent (get_agent_for_contact): should_response: {should_response} | Agent: None | Device Id: {device_id} | Contact Id: {contact_id}")
        
        if agent and should_response == False and agent.type == AgentType.PERSONAL:
            logger.info(f"Agente PESSOAL sem permissão para o contato {contact_id} do dispositivo {device_id} do tenant {tenant_id}. Ignorando mensagem mensagem direcionada ao agentet | Agent (get_agent_for_contact): should_response: {should_response} | Agent: {agent.id} ({agent.name}")
            print(f"Agente PESSOAL sem permissão para o contato {contact_id} do dispositivo {device_id} do tenant {tenant_id}. Ignorando mensagem mensagem direcionada ao agentet | Agent (get_agent_for_contact): should_response: {should_response} | Agent: {agent.id} ({agent.name}")
            return
        
        if not agent:
            logger.warning(f"Nenhum agente encontrado para o contato {contact_id} do dispositivo {device_id} do tenant {tenant_id}")
            print(f"Nenhum agente encontrado para o contato {contact_id} do dispositivo {device_id} do tenant {tenant_id}")

            if should_response == False:
                # Ignorar mensagens sem agente
                logger.warning(f"Mensagem sem agente para o contato {contact_id} do dispositivo {device_id} do tenant {tenant_id}. Sera ignorada")
                print(f"Mensagem sem agente para o contato {contact_id} do dispositivo {device_id} do tenant {tenant_id}. Sera ignorada")
                return
                
            
            agent = await agent_service.get_agent_for_device(device_id, tenant_id)
        
            if not agent:
                logger.warning(f"Nenhum agente encontrado para o dispositivo {device_id} do tenant {tenant_id}")
                print(f"Nenhum agente encontrado para o dispositivo {device_id} do tenant {tenant_id}")

                # Buscar agente geral ativo para este tenant
                agent_query = (
                    db.query(Agent)
                    .filter(
                        Agent.tenant_id == tenant_id,
                        Agent.type == 'general',
                        Agent.active == True
                    )
                    .first()
                )
                
                if not agent_query:
                    logger.warning(f"Nenhum agente geral ativo encontrado para o tenant {tenant_id}")
                    print(f"Nenhum agente geral ativo encontrado para o tenant {tenant_id}")
                    return
                
                agent = agent_service._db_to_schema(agent_query)
                
                if not agent:
                    logger.warning(f"Nenhum agente geral ativo encontrado para o tenant {tenant_id}")
                    print(f"Nenhum agente geral ativo encontrado para o tenant {tenant_id}")
                    return 
        
        
        # Inicializar serviços
        llm_service = await get_llm_service(db, str(tenant_id) if tenant_id else None) #LLMService(api_key=os.getenv("OPENAI_API_KEY"))
        rag_service = RAGServiceFAISS(tenant_id=tenant_id)
        
        if has_valid_audio and not llm_supports_audio(llm_service):
            # Log do processamento
            log_audio_processing(
                device_id=device_id,
                chat_jid=chat_jid,
                audio_size=audio_info.get("size_estimate", 0),
                llm_type=type(llm_service).__name__,
                success=False,
                error="LLM does not support audio"
            )
            
            # Responder com mensagem padrão
            response_message = get_audio_not_supported_response(agent.name if agent else None)
            
            await whatsapp_service.send_message(
                device_id=device_id,
                to=chat_jid,
                message=response_message
            )
            logger.info(f"Audio not supported response sent to {chat_jid}")
            return
        
        # Log de sucesso se áudio será processado
        if has_valid_audio:
            log_audio_processing(
                device_id=device_id,
                chat_jid=chat_jid,
                audio_size=audio_info.get("size_estimate", 0),
                llm_type=type(llm_service).__name__,
                success=True
            )
       
        
        # Preparar conteúdo da mensagem
        event_message = data.get("event", {}).get("Message", {})
        message_content = event_message.get("Conversation", "")
        
        if not message_content:
            # Tentar extrair de outros tipos de mensagem
            if ext_text := event_message.get("ExtendedTextMessage", {}):
                message_content = ext_text.get("Text", "")
        
        # Se é áudio, obter transcrição primeiro
        if has_valid_audio:
            try:
                transcription = await llm_service.get_audio_transcription(audio_info)
                if transcription:
                    if message_content:
                        message_content = f"{message_content} [Áudio transcrito: {transcription}]"
                    else:
                        message_content = f"[Mensagem de áudio] {transcription}"
                else:
                    message_content = message_content or "[Mensagem de áudio - transcrição não disponível]"
            except Exception as e:
                logger.warning(f"Erro ao transcrever áudio: {e}")
                message_content = message_content or "[Mensagem de áudio - erro na transcrição]"
        
        
        # Criar o serviço de contagem de tokens (novo)
        token_counter_service = TokenCounterService(db)
        
        if whatsapp_service == None:
            whatsapp_service = WhatsAppService()
        
        # Configuração do sistema
        config = load_system_config()
        
        # Inicializar orquestrador
        orchestrator = AgentOrchestrator(agent_service, rag_service, redis_client, llm_service, config, token_counter_service)
        
        
        # Verificar se já existe uma conversa para este usuário
        conversation_key = f"whatsapp_conversation:{tenant_id}:{chat_jid}"
        conversation_id = await redis_client.get(conversation_key) if redis_client else None
        
        print(f"[DEBUG] Chave recuperada: {conversation_key}")
        print(f"[DEBUG] ID recuperado: {conversation_id}, tipo: {type(conversation_id)}")
        
        # Converter para string se for bytes
        if conversation_id and isinstance(conversation_id, bytes):
            conversation_id = conversation_id.decode('utf-8')
            print(f"[DEBUG] ID após decodificação: {conversation_id}")
        
        # Se não existir, iniciar uma nova conversa
        if not conversation_id:
            # Usar chat_jid como identificador do usuário
            conversation_id = await orchestrator.start_conversation(str(tenant_id), chat_jid, agent_id=agent.id)
            print(f"[DEBUG] Nova conversa criada: {conversation_id}")
            
            # Armazenar o ID da conversa para futuras mensagens
            if redis_client:
                await redis_client.set(conversation_key, conversation_id)
                await redis_client.expire(conversation_key, 60 * 60 * 24)  # Expira em 24 horas
                print(f"[DEBUG] ID armazenado no Redis com chave: {conversation_key}")
        
        # Always update the mapping with a longer TTL
        await orchestrator.map_user_to_conversation(str(tenant_id), chat_jid, conversation_id)
        
        # Also update the standard key for backward compatibility
        conversation_key = f"whatsapp_conversation:{tenant_id}:{chat_jid}"
        await redis_client.set(conversation_key, conversation_id)
        await redis_client.expire(conversation_key, 60 * 60 * 24)  # 24 hours
       
        
        result = await orchestrator.process_message(
            conversation_id, 
            message_content, 
            agent_id=agent.id, 
            contact_id=contact_id
        )
        
        # Check if the conversation ID changed (due to timeout/limit reset)
        if result.get("new_conversation_id") and result.get("new_conversation_id") != conversation_id:
            # Update the mapping with the new conversation ID
            new_id = result.get("new_conversation_id")
            await orchestrator.map_user_to_conversation(str(tenant_id), chat_jid, new_id)
            
            # Update standard key too
            await redis_client.set(conversation_key, new_id)
            await redis_client.expire(conversation_key, 60 * 60 * 24)
        
        # Enviar resposta via WhatsApp
        if "response" in result and result["response"].strip():
            await whatsapp_service.send_message(
                device_id=device_id,
                to=chat_jid,
                message=result["response"]
            )
            logger.info(f"Resposta enviada para {chat_jid}: {result['response'][:50]}...")
        
        elif "error_audio_processing" in result:
            
                # Responder com mensagem padrão de audio não processado
                response_message_audio = get_audio_error_response(agent.name if agent else None)
                
                await whatsapp_service.send_message(
                    device_id=device_id,
                    to=chat_jid,
                    message=response_message_audio
                )
        
        else:
            logger.warning(f"Resposta não encontrada para {chat_jid}: {result}")
            
            # Responder com mensagem padrão
            response_message_audio = get_error_response_generic(agent.name if agent else None)
            
            await whatsapp_service.send_message(
                device_id=device_id,
                to=chat_jid,
                message=response_message_audio
            )
        
        
        # Processar ações especiais, como escalação para humano
        if "actions" in result:
            for action in result["actions"]:
                if action["type"] == "human_escalation":
                    escalation_contact = action["contact"]
                    
                    escalation_contacts = [escalation_contact]
                    
                    if escalation_contact is not None and "#" in escalation_contact:
                        escalation_contacts = escalation_contact.split("#")
                        
                    # iterar sobre os contatos e enviar uma mensagem para cada um
                    for escalation_contact in escalation_contacts:
                        escalation_contact = escalation_contact.strip()    
                        
                        logger.info(f"Enviando mensagem de escalação para {escalation_contact}")
                        
                        # Formatar o contato de escalação
                        try:
                            escalation_contact =format_whatsapp_number(escalation_contact)
                            print(f"Contato de escalação: {escalation_contact}")
                            
                            # Extrair número do cliente a partir do chat_jid
                            client_number = chat_jid.replace('@s.whatsapp.net', '')
                            print(f"Número do cliente: {client_number}")
                            
                            # Montar link clicável para abrir chat com o cliente
                            wa_link = f"https://wa.me/{client_number}"
                            
                            conversation_summary = action["conversation_summary"]
                        
                            escalation_message = (
                                f"🔔 *ESCALAÇÃO PARA ATENDIMENTO HUMANO*\n\n"
                                f"Um cliente solicitou atendimento humano.\n\n"
                                f"*Resumo da conversa:*\n{conversation_summary}\n\n"
                                f"Telefone do cliente: {client_number}\n"
                                f"👉 Clique para abrir o WhatsApp: {wa_link}\n\n"
                                f"Por favor, entre em contato com o cliente."
                            )
                            
                            try:
                                # Enviar para o contato de escalação
                                await whatsapp_service.send_message(
                                    device_id=device_id,
                                    to=escalation_contact,
                                    message=escalation_message
                                )
                            
                                # Informar ao cliente que a escalação foi realizada
                                await whatsapp_service.send_message(
                                    device_id=device_id,
                                    to=chat_jid,
                                    message="Sua solicitação foi encaminhada para um atendente. Em breve alguém entrará em contato."
                                )
                            except Exception as e:
                                logger.error(f"Erro ao enviar mensagem para o contato de escalação: {e}")
                                print(f"Erro ao enviar mensagem para o contato de escalação: {e}")
                                
                                # TODO implementar mensagem de erro para um contato de administração
                                # await whatsapp_service.send_message(
                                #         device_id=device_id,
                                #         to=chat_jid_administracao,
                                #         message="Não foi possível encaminhar a solicitação do cliente {{chat_jid}} para um atendente {{escalation_contact}} agora. Verifique para mais detalhes."
                                #     )
                                
                                # Informar ao cliente que a escalação foi realizada
                                await whatsapp_service.send_message(
                                    device_id=device_id,
                                    to=chat_jid,
                                    message="Infelizmente, não foi possível encaminhar sua solicitação para um atendente agora. Peço que tente novamente mais tarde."
                                )
                            
                        except ValueError as e:
                            logger.error(f"Erro ao formatar o contato de escalação '{escalation_contact}': {e}")
                            print(f"Erro ao formatar o contato de escalação '{escalation_contact}': {e}")
                            
                            # TODO implementar mensagem de erro para um contato de administração
                            # await whatsapp_service.send_message(
                            #         device_id=device_id,
                            #         to=chat_jid_administracao,
                            #         message=message="Não foi possível encaminhar a solicitação do cliente {{chat_jid}} para um atendente {{escalation_contact}} agora. Verifique para mais detalhes."
                            #     )
                            
                            await whatsapp_service.send_message(
                                    device_id=device_id,
                                    to=chat_jid,
                                    message="Infelizmente, não foi possível encaminhar sua solicitação para um atendente agora. Peço que tente novamente mais tarde."
                                )
                            
                        
                        # Enviar notificação para o contato de escalação
                    
        #Processar continuações automáticas
        if result.get("requires_continuation", False):
            logger.info(f"Requisitando continuação para conversa {conversation_id}")    
            continuation_delay = result.get("continuation_delay", 5)
            logger.info(f"Delay de continuação para conversa {conversation_id}: {continuation_delay}s")
            # Agendar continuação após delay
            asyncio.create_task(
                send_continuation_message(
                    conversation_id=conversation_id,
                    delay=continuation_delay,
                    whatsapp_service=whatsapp_service,
                    device_id=device_id,
                    chat_jid=chat_jid,
                    orchestrator=orchestrator,
                    tenant_id=tenant_id
                )
            )
            logger.info(f"Continuação agendada para conversa {conversation_id} em {continuation_delay}s")
        
                    
        
        # Processar webhooks para este evento
        # (código existente para processamento de webhooks)
        tenant_webhooks = db.query(Webhook).filter(
            Webhook.tenant_id == tenant_id,
            Webhook.enabled == True
        ).all()
        
        for webhook in tenant_webhooks:
            webhook_events = json.loads(webhook.events) if webhook.events else []
            if not webhook_events or "*" in webhook_events or "*events.Message" in webhook_events:
                webhook_devices = json.loads(webhook.device_ids) if webhook.device_ids else []
                if not webhook_devices or device_id in webhook_devices:
                    await send_webhook_request(webhook, data, db)
        
    except Exception as e:
        logger.error(f"Erro ao processar mensagem do WhatsApp: {e}")
        logger.exception(e)
        

# def _llm_supports_audio(llm_service) -> bool:
#     """Verifica se o serviço LLM suporta processamento de áudio."""
#     from app.services.llm.gemini_service import GeminiService
    
#     # Apenas Gemini suporta áudio por enquanto # TODO add mais serviços quando for necessário
#     return isinstance(llm_service, GeminiService)

# 1. Mapeamento de especialidades para categorias de foco
SPECIALTY_TO_FOCUS_MAPPING = {
    # Comercial/Vendas
    "commercial": ["commercial", "product_info", "billing", "professional"],
    "marketing": ["commercial", "product_info", "retail"],
    "sales": ["commercial", "product_info", "billing"],
    "customer_service": ["general", "complaint", "product_info"],
    
    # Suporte Técnico
    "support": ["support", "technical_issue", "technology"],
    "it": ["technology", "technical_issue", "support"],
    "software_development": ["technology", "technical_issue"],
    "web_development": ["technology", "technical_issue"],
    "mobile_development": ["technology", "technical_issue"],
    
    # Saúde
    "healthcare": ["healthcare"],
    "medical_exams": ["healthcare", "appointment"],
    "health_insurance": ["healthcare", "billing"],
    
    # Varejo
    "retail": ["retail", "billing", "product_info"],
    "order_tracking": ["retail", "logistics"],
    "returns": ["retail", "complaint"],
    
    # Outros domínios
    "sports": ["sports"],
    "crafts": ["crafts"],
    "professional_services": ["professional"],
    "finance": ["finance", "billing"],
    "accounting": ["finance", "billing"],
    "tourism": ["tourism"],
    "hotel": ["tourism", "appointment"],
    "education": ["education"],
    "courses": ["education"],
    "real_estate": ["real_estate"],
    "rental": ["real_estate", "billing"],
    "automotive": ["automotive", "technical_issue"],
    "maintenance": ["automotive", "technical_issue"],
    "logistics": ["logistics"],
    "shipping": ["logistics"],
    "events": ["events", "appointment"],
    "entertainment": ["events"],
    "pets": ["pets"],
    "veterinary": ["pets", "healthcare"],
    "wellness": ["wellness", "healthcare"],
    "beauty": ["wellness"],
    "technology": ["technology", "technical_issue"],
    "it_support": ["technology", "technical_issue", "support"],
    "legal": ["legal", "professional"],
    "law": ["legal", "professional"]
}

# 2. Templates de resposta por categoria de foco
FOCUS_RESPONSE_TEMPLATES = {
    "commercial": {
        "question_detected": "Olá! Sou {agent_name}. Vi que você perguntou sobre {context_hint}. Vou te ajudar com todas as informações comerciais!",
        "clear_intent": "Oi! Sou {agent_name}, especialista comercial. Sobre {intent_context}, posso te dar todos os detalhes!",
        "standard": "Olá! Sou {agent_name} e vou ajudá-lo com todas as informações comerciais sobre nossos produtos e serviços!"
    },
    
    "support": {
        "question_detected": "Olá! Sou {agent_name} do suporte. Vi que você está com {context_hint}. Vou te ajudar a resolver!",
        "clear_intent": "Oi! Sou {agent_name} da equipe técnica. Sobre {intent_context}, vou te orientar passo a passo!",
        "standard": "Olá! Sou {agent_name} da equipe de suporte técnico. Vou ajudá-lo a resolver qualquer questão!"
    },
    
    "technical_issue": {
        "question_detected": "Olá! Sou {agent_name}. Vi que você está enfrentando {context_hint}. Vamos resolver isso!",
        "clear_intent": "Oi! Sou {agent_name}. Sobre {intent_context}, vou te ajudar com a solução!",
        "standard": "Olá! Sou {agent_name} e vou ajudá-lo a resolver questões técnicas!"
    },
    
    "healthcare": {
        "question_detected": "Olá! Sou {agent_name}. Sobre {context_hint}, posso te ajudar com informações e orientações!",
        "clear_intent": "Oi! Sou {agent_name}. Quanto a {intent_context}, vou te dar todo o suporte necessário!",
        "standard": "Olá! Sou {agent_name} e estou aqui para ajudá-lo com questões de saúde!"
    },
    
    "retail": {
        "question_detected": "Olá! Sou {agent_name}. Vi sua pergunta sobre {context_hint}. Vou te ajudar com seu pedido!",
        "clear_intent": "Oi! Sou {agent_name}. Sobre {intent_context}, posso te dar todas as informações!",
        "standard": "Olá! Sou {agent_name} e vou ajudá-lo com suas compras e pedidos!"
    },
    
    "finance": {
        "question_detected": "Olá! Sou {agent_name}. Sobre {context_hint}, posso esclarecer todas suas dúvidas financeiras!",
        "clear_intent": "Oi! Sou {agent_name}. Quanto a {intent_context}, vou te orientar sobre as melhores opções!",
        "standard": "Olá! Sou {agent_name} e vou ajudá-lo com questões financeiras!"
    },
    
    # Template genérico para outras categorias
    "default": {
        "question_detected": "Olá! Sou {agent_name}. Vi sua pergunta sobre {context_hint}. Vou te ajudar!",
        "clear_intent": "Oi! Sou {agent_name}. Sobre {intent_context}, posso te dar todo o suporte!",
        "standard": "Olá! Sou {agent_name} e vou continuar nosso atendimento. Como posso ajudá-lo?"
    }
}

#função para processar continuações
async def send_continuation_message(conversation_id: str, delay: int, 
                                           whatsapp_service: WhatsAppService,
                                           device_id: str, chat_jid: str,
                                           orchestrator, tenant_id: str):
    """
    Versão flexível que utiliza a análise de foco existente para determinar continuação.
    """
    try:
        await asyncio.sleep(delay)
        
        # Buscar estado da conversa
        state = await orchestrator.get_conversation_state(conversation_id)
        if not state:
            logger.error(f"Estado da conversa {conversation_id} não encontrado para continuação")
            return
        
        # Obter agente atual
        current_agent = orchestrator.agent_service.get_agent(state.current_agent_id)
        if not current_agent:
            logger.error(f"Agente {state.current_agent_id} não encontrado para continuação")
            return
        
        # Analisar contexto usando a função existente
        context_analysis = await _analyze_conversation_context_flexible(
            state, current_agent, orchestrator
        )
        
        # Gerar mensagem baseada na análise
        continuation_message = _generate_flexible_continuation_message(
            context_analysis, current_agent
        )
        
        # abordagem flexivel
        logger.info(f"Continuação flexível: {continuation_message[:100]}...")
        
        # Processar mensagem
        continuation_result = await orchestrator.process_message(
            conversation_id=conversation_id,
            message="",
            agent_id=current_agent.id,     
            contact_id=state.user_id,        
            audio_data=None                
        )
        
        # Enviar via WhatsApp
        if continuation_result.get("response"):
            await whatsapp_service.send_message(
                device_id=device_id,
                to=chat_jid,
                message=continuation_result["response"]
            )
            logger.info(f"Continuação flexível enviada para {chat_jid}")
            
        
        # # abordagem direta # TODO testar se necessário
        # logger.info(f"Continuação direta: {continuation_message[:100]}...")
        
        # # Adicionar mensagem diretamente ao histórico
        # state.history.append({
        #     "role": "assistant",
        #     "content": continuation_message,
        #     "timestamp": time.time(),
        #     "agent_id": current_agent.id,
        #     "continuation": True  # Flag para identificar mensagens de continuação
        # })
        
        # # Atualizar estado
        # state.last_updated = time.time()
        # await orchestrator.save_conversation_state(state)
        
        # # Enviar via WhatsApp diretamente
        # await whatsapp_service.send_message(
        #     device_id=device_id,
        #     to=chat_jid,
        #     message=continuation_message
        # )
        
        # logger.info(f"Continuação direta enviada para {chat_jid}")
        
    except Exception as e:
        logger.error(f"Erro na continuação flexível para {conversation_id}: {e}")


async def _analyze_conversation_context_flexible(state: ConversationState, 
                                               current_agent: Agent, 
                                               orchestrator) -> Dict[str, Any]:
    """
    Análise de contexto flexível usando a lógica de _analyze_conversation_focus.
    """
    
    # Obter últimas mensagens do usuário
    user_messages = [
        msg for msg in state.history[-10:] 
        if msg.get("role") == "user"
    ][-5:]
    
    if not user_messages:
        return {
            "has_pending_question": False,
            "has_clear_intent": False,
            "user_context": "",
            "focus_analysis": {},
            "dominant_category": "general",
            "agent_specialties": current_agent.specialties
        }
    
    last_user_message = user_messages[-1].get("content", "")
    
    # Usar a função existente para analisar o foco
    focus_analysis = await orchestrator._analyze_conversation_focus(
        user_messages, last_user_message
    )
    
    # Identificar categoria dominante
    dominant_category = max(focus_analysis.items(), key=lambda x: x[1])[0]
    
    # Detectar perguntas
    question_indicators = [
        "?", "quanto", "como", "onde", "quando", "por que", "porque", 
        "qual", "quais", "posso", "consegue", "tem", "existe", "funciona"
    ]
    
    has_question = any(indicator in last_user_message.lower() for indicator in question_indicators)
    
    # Verificar compatibilidade entre agente e foco da conversa
    agent_compatibility = _check_agent_focus_compatibility(current_agent, focus_analysis)
    
    # Extrair contexto semântico
    context_hints = _extract_semantic_context(last_user_message, focus_analysis)
    
    return {
        "has_pending_question": has_question,
        "has_clear_intent": agent_compatibility["is_compatible"],
        "user_context": last_user_message,
        "focus_analysis": focus_analysis,
        "dominant_category": dominant_category,
        "agent_specialties": current_agent.specialties,
        "agent_compatibility": agent_compatibility,
        "context_hints": context_hints,
        "conversation_stage": _determine_conversation_stage_flexible(user_messages)
    }


def _check_agent_focus_compatibility(current_agent: Agent, focus_analysis: Dict[str, float]) -> Dict[str, Any]:
    """
    Verifica compatibilidade entre especialidades do agente e foco da conversa.
    """
    if not current_agent.specialties:
        return {"is_compatible": False, "compatibility_score": 0.0, "matched_categories": []}
    
    # Mapear especialidades para categorias de foco
    agent_focus_categories = []
    for specialty in current_agent.specialties:
        if specialty in SPECIALTY_TO_FOCUS_MAPPING:
            agent_focus_categories.extend(SPECIALTY_TO_FOCUS_MAPPING[specialty])
    
    # Calcular score de compatibilidade
    compatibility_score = 0.0
    matched_categories = []
    
    for category in agent_focus_categories:
        if category in focus_analysis and focus_analysis[category] > 0.1:  # Threshold mínimo
            compatibility_score += focus_analysis[category]
            matched_categories.append(category)
    
    return {
        "is_compatible": compatibility_score > 0.2,  # Threshold de compatibilidade
        "compatibility_score": compatibility_score,
        "matched_categories": matched_categories,
        "agent_focus_categories": agent_focus_categories
    }


def _extract_semantic_context(message: str, focus_analysis: Dict[str, float]) -> Dict[str, Any]:
    """
    Extrai contexto semântico da mensagem baseado na análise de foco.
    """
    message_lower = message.lower()
    
    # Identificar elementos específicos baseados na categoria dominante
    context_elements = {
        "pricing_keywords": ["preço", "valor", "custo", "quanto"],
        "problem_keywords": ["problema", "erro", "não funciona", "quebrou"],
        "service_keywords": ["como funciona", "preciso", "quero", "gostaria"],
        "urgency_keywords": ["urgente", "rápido", "agora", "imediato"]
    }
    
    detected_elements = {}
    for element_type, keywords in context_elements.items():
        detected_elements[element_type] = [kw for kw in keywords if kw in message_lower]
    
    # Gerar hint contextual baseado nos elementos detectados
    context_hint = _generate_context_hint(detected_elements, focus_analysis)
    
    return {
        "detected_elements": detected_elements,
        "context_hint": context_hint,
        "message_sentiment": _analyze_message_sentiment(message_lower)
    }


def _generate_context_hint(detected_elements: Dict, focus_analysis: Dict[str, float]) -> str:
    """
    Gera hint contextual para usar nas respostas.
    """
    if detected_elements["pricing_keywords"]:
        return "preços e condições"
    elif detected_elements["problem_keywords"]:
        return "um problema técnico"
    elif detected_elements["service_keywords"]:
        return "informações sobre nossos serviços"
    elif max(focus_analysis.values()) > 0.3:
        # Usar categoria dominante
        dominant = max(focus_analysis.items(), key=lambda x: x[1])[0]
        return f"questões de {dominant}"
    else:
        return "sua solicitação"


def _analyze_message_sentiment(message: str) -> str:
    """
    Análise simples de sentimento da mensagem.
    """
    negative_words = ["problema", "erro", "ruim", "péssimo", "não funciona", "irritado"]
    positive_words = ["bom", "ótimo", "obrigado", "excelente", "perfeito"]
    urgent_words = ["urgente", "rápido", "agora", "imediato"]
    
    if any(word in message for word in urgent_words):
        return "urgent"
    elif any(word in message for word in negative_words):
        return "negative"
    elif any(word in message for word in positive_words):
        return "positive"
    else:
        return "neutral"


def _determine_conversation_stage_flexible(user_messages: List[Dict]) -> str:
    """
    Determina estágio da conversa de forma flexível.
    """
    message_count = len(user_messages)
    
    if message_count <= 1:
        return "initial"
    elif message_count <= 3:
        return "exploration"
    elif message_count <= 6:
        return "engagement"
    else:
        return "advanced"


def _generate_flexible_continuation_message(context_analysis: Dict, current_agent: Agent) -> str:
    """
    Gera mensagem de continuação baseada na análise flexível.
    """
    agent_name = current_agent.name
    dominant_category = context_analysis["dominant_category"]
    context_hints = context_analysis["context_hints"]
    agent_compatibility = context_analysis["agent_compatibility"]
    
    # Selecionar template baseado na compatibilidade e categoria
    if agent_compatibility["is_compatible"]:
        # Agente é compatível com o foco da conversa
        matched_categories = agent_compatibility["matched_categories"]
        primary_category = matched_categories[0] if matched_categories else dominant_category
    else:
        # Usar categoria dominante ou fallback
        primary_category = dominant_category if dominant_category != "general" else "default"
    
    # Obter templates para a categoria
    templates = FOCUS_RESPONSE_TEMPLATES.get(primary_category, FOCUS_RESPONSE_TEMPLATES["default"])
    
    # Escolher tipo de resposta
    if context_analysis["has_pending_question"]:
        template = templates["question_detected"]
        context_hint = context_hints["context_hint"]
    elif context_analysis["has_clear_intent"]:
        template = templates["clear_intent"]
        context_hint = context_hints["context_hint"]
    else:
        template = templates["standard"]
        context_hint = ""
    
    # Formatear mensagem
    try:
        if context_hint:
            return template.format(
                agent_name=agent_name,
                context_hint=context_hint,
                intent_context=context_hint
            )
        else:
            return template.format(agent_name=agent_name)
    except KeyError:
        # Fallback para template simples
        return f"Olá! Sou {agent_name} e vou continuar nosso atendimento. Como posso ajudá-lo?"


# 3. Função auxiliar para debug e monitoramento
def log_continuation_analysis(context_analysis: Dict, current_agent: Agent):
    """
    Log detalhado para debug da análise de continuação.
    """
    logger.info(f"=== ANÁLISE DE CONTINUAÇÃO ===")
    logger.info(f"Agente: {current_agent.name} | Especialidades: {current_agent.specialties}")
    logger.info(f"Categoria dominante: {context_analysis['dominant_category']}")
    logger.info(f"Compatibilidade: {context_analysis['agent_compatibility']['is_compatible']}")
    logger.info(f"Score: {context_analysis['agent_compatibility']['compatibility_score']:.2f}")
    logger.info(f"Categorias matched: {context_analysis['agent_compatibility']['matched_categories']}")
    logger.info(f"Context hint: {context_analysis['context_hints']['context_hint']}")
    logger.info(f"Estágio: {context_analysis['conversation_stage']}")
    logger.info(f"===========================")
    
def format_whatsapp_number(raw_number):
    # Remover tudo que não for número
    digits = re.sub(r'\D', '', raw_number)

    # Verificar se já começa com 55 (DDI Brasil)
    if digits.startswith("55"):
        number_without_ddi = digits[2:]
    else:
        number_without_ddi = digits

    # Agora validar se sobrou exatamente 10 dígitos (2 do DDD + 8 do número)
    if len(number_without_ddi) != 10:
        raise ValueError("Número inválido. O número deve ter DDD (2 dígitos) + número (8 dígitos).")

    # Montar no formato final
    formatted_number = f"55{number_without_ddi}@s.whatsapp.net"
    return formatted_number

async def process_whatsapp_message_simplified(data: Dict[str, Any], whatsapp_service: WhatsAppService, db: Session):
    """
    Process messages received from WhatsApp
    """
    try:
        # Extract message information
        device_id = data.get("device_id")
        tenant_id = data.get("tenant_id")
        event = data.get("event", {})
        
        # Ignore messages sent by the device itself
        if event.get("Info", {}).get("IsFromMe"):
            return
        
        # Extract message information
        sender = event.get("Info", {}).get("Sender", {})
        chat_jid = event.get("Info", {}).get("Chat")
        message_content = event.get("Message", {}).get("Conversation")
        
        if not message_content:
            # Try to extract from other message types
            if ext_text := event.get("Message", {}).get("ExtendedTextMessage", {}):
                message_content = ext_text.get("Text", "")
        
        if not message_content:
            # Ignore messages without text content
            return
        
        # Initialize RAG service with the correct tenant_id
        rag_service = RAGServiceFAISS(tenant_id=tenant_id)
        
        # Try to detect category based on content
        category = detect_category(message_content)
        
        # Check if it's a question or command
        if message_content.strip().endswith("?") or is_command(message_content):
            # Get context using RAG, filtering by category if detected
            context = await rag_service.get_context(message_content, category=category)
            
            # Generate response
            answer = await rag_service.get_answer(message_content, context)
            
            if answer:
                # Send response via WhatsApp
                await whatsapp_service.send_message(
                    device_id=device_id,
                    to=chat_jid,
                    message=answer
                )
                logger.info(f"Response sent to {chat_jid}: {answer[:50]}...")
        
        # Send webhook notifications for this message
        tenant_webhooks = db.query(Webhook).filter(
            Webhook.tenant_id == tenant_id,
            Webhook.enabled == True
        ).all()
        
        # Process webhooks in background (ideally would use a proper queue system)
        for webhook in tenant_webhooks:
            # Check if this webhook should receive message events
            webhook_events = json.loads(webhook.events) if webhook.events else []
            if not webhook_events or "*" in webhook_events or "*events.Message" in webhook_events:
                # Check if webhook is configured for this device
                webhook_devices = json.loads(webhook.device_ids) if webhook.device_ids else []
                if not webhook_devices or device_id in webhook_devices:
                    # Send webhook
                    await send_webhook_request(webhook, data, db)
        
    except Exception as e:
        logger.error(f"Error processing WhatsApp message: {e}")


async def send_webhook_request(webhook: Webhook, data: Dict[str, Any], db: Session):
    """
    Send a webhook request with retries
    """
    import httpx
    
    # Prepare webhook log
    log = WebhookLog(
        id=str(uuid.uuid4()),
        webhook_id=webhook.id,
        status="pending",
        event_type=data.get("event_type", "unknown"),
        attempt_count=0,
        payload=json.dumps(data)
    )
    
    db.add(log)
    db.commit()
    
    # Prepare request
    url = webhook.url
    headers = {
        "Content-Type": "application/json",
        "X-Webhook-ID": webhook.id,
        "X-Event-Type": data.get("event_type", "unknown"),
        "X-Timestamp": str(time.time())
    }
    
    # Add signature if secret is configured
    if webhook.secret:
        payload_bytes = json.dumps(data).encode('utf-8')
        signature = hmac.new(
            webhook.secret.encode('utf-8'), 
            payload_bytes, 
            hashlib.sha256
        ).hexdigest()
        headers["X-Webhook-Signature"] = signature
    
    # Retry parameters
    max_attempts = 3
    attempt = 0
    backoff = 1  # initial backoff in seconds
    
    while attempt < max_attempts:
        attempt += 1
        log.attempt_count = attempt
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json=data,
                    headers=headers,
                    timeout=10.0
                )
                
                # Update log with response
                log.response_code = response.status_code
                log.response_body = response.text[:1000]  # Limit response size
                
                if 200 <= response.status_code < 300:
                    log.status = "success"
                    db.commit()
                    return
                
                # Failed but got a response
                log.status = "failed"
                log.error_message = f"HTTP {response.status_code}: {response.text[:200]}"
                
        except Exception as e:
            # Connection error or timeout
            log.status = "failed"
            log.error_message = str(e)[:500]  # Limit error message size
        
        # If this isn't the last attempt, mark as retrying
        if attempt < max_attempts:
            log.status = "retrying"
            db.commit()
            
            # Exponential backoff
            await asyncio.sleep(backoff)
            backoff *= 2
        else:
            # Final failure
            db.commit()


def detect_category(text: str) -> Optional[str]:
    """
    Detect the most likely category based on message content
    """
    # Possible categories
    categories = {
        "atendimento": ["atendimento", "recepção", "ajuda", "suporte", "dúvida"],
        "consultas": ["agendar", "consulta", "horário", "marcar", "reagendar", "desmarca"],
        "procedimentos": ["procedimento", "tratamento", "canal", "extração", "limpeza", "clareamento"],
        "preços": ["preço", "valor", "custo", "orçamento", "pagamento", "parcela"],
        "urgência": ["dor", "urgente", "emergência", "sangramento", "acidente"]
    }
    
    text_lower = text.lower()
    
    # Score for each category
    scores = {category: 0 for category in categories}
    
    # Calculate score
    for category, keywords in categories.items():
        for keyword in keywords:
            if keyword in text_lower:
                scores[category] += 1
    
    # Find category with highest score
    best_category = max(scores.items(), key=lambda x: x[1])
    
    # Return highest scoring category, if it has any occurrences
    if best_category[1] > 0:
        return best_category[0]
    
    return None


def is_command(text: str) -> bool:
    """
    Check if the text is a command for the assistant
    """
    commands = ["agendar", "consulta", "horário", "horarios", "preço", 
                "valor", "ajuda", "info", "informação", "marcar"]
    
    lower_text = text.lower()
    
    # Check if text starts with any command or contains it surrounded by spaces
    for command in commands:
        if lower_text.startswith(command) or f" {command} " in f" {lower_text} ":
            return True
    
    return False