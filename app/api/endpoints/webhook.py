import hashlib
import hmac
import logging
import asyncio
from typing import Dict, Any, Optional, List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Path, Query
from sqlalchemy.orm import Session
import uuid
import json
import time
from datetime import datetime

from app.api.deps import get_db, get_tenant_id, get_whatsapp_service
from app.services.rag import RAGService
from app.services.whatsapp import WhatsAppService
from app.db.models.webhook import Webhook, WebhookLog
from app.schemas.webhook import WebhookCreate, WebhookResponse, WebhookLogResponse
from app.api.utils.webhook_processor import process_whatsapp_message, send_webhook_request

router = APIRouter()
logger = logging.getLogger(__name__)


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
        # Create webhook
        new_webhook = Webhook(
            id=str(uuid.uuid4()),
            url=webhook.url,
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
            url=new_webhook.url,
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

async def process_whatsapp_message(data: Dict[str, Any], whatsapp_service: WhatsAppService, db: Session):
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
        
        # Initialize RAG service with the correct tenant_id
        rag_service = RAGService(tenant_id=tenant_id)
        
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