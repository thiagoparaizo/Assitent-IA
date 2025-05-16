import json
import logging
import hmac
import hashlib
import time
import asyncio
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models.webhook import Webhook, WebhookLog
from app.services.rag_faiss import RAGServiceFAISS
from app.services.whatsapp import WhatsAppService
#from app.services.rag import RAGService

logger = logging.getLogger(__name__)

async def process_whatsapp_message(data: Dict[str, Any], whatsapp_service: Optional[WhatsAppService], db: Session):
    """
    Processa mensagens recebidas do WhatsApp e envia resposta usando RAG se necessário.
    Esta função também envia notificações webhook para tenants configurados.
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
        sender = event.get("Info", {}).get("Sender", {}).get("User")
        chat_jid = event.get("Info", {}).get("Chat")
        message_content = event.get("Message", {}).get("Conversation")
        
        if not message_content:
            # Try to extract from other message types
            if ext_text := event.get("Message", {}).get("ExtendedTextMessage", {}):
                message_content = ext_text.get("Text", "")
        
        if not message_content:
            # Ignore messages without text content
            return
        
        # Se temos um tenant_id e conteúdo de mensagem, vamos processar
        if tenant_id and message_content:
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
                
                # Se temos uma resposta e o serviço de WhatsApp está disponível
                if answer and whatsapp_service:
                    # Send response via WhatsApp
                    await whatsapp_service.send_message(
                        device_id=device_id,
                        to=chat_jid,
                        message=answer
                    )
                    logger.info(f"Response sent to {chat_jid}: {answer[:50]}...")
        
        # Processar webhooks para este evento (enviar para clientes externos)
        await process_tenant_webhooks(tenant_id, data, db)
        
    except Exception as e:
        logger.error(f"Error processing WhatsApp message: {e}")


async def process_tenant_webhooks(tenant_id: int, data: Dict[str, Any], db: Session):
    """
    Processa webhooks para um determinado evento
    """
    if not tenant_id:
        return
        
    # Buscar webhooks ativos para este tenant
    tenant_webhooks = db.query(Webhook).filter(
        Webhook.tenant_id == tenant_id,
        Webhook.enabled == True
    ).all()
    
    device_id = data.get("device_id")
    event_type = data.get("event_type")
    
    # Processar cada webhook em paralelo
    tasks = []
    for webhook in tenant_webhooks:
        # Verificar se este webhook deve receber este tipo de evento
        webhook_events = json.loads(webhook.events) if webhook.events else []
        if not webhook_events or "*" in webhook_events or event_type in webhook_events:
            # Verificar se webhook é configurado para este dispositivo
            webhook_devices = json.loads(webhook.device_ids) if webhook.device_ids else []
            if not webhook_devices or device_id in webhook_devices:
                # Criar task para enviar webhook
                tasks.append(send_webhook_request(webhook, data, db))
    
    # Executar todos os envios em paralelo
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


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