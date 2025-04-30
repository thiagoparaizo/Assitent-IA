import logging
from typing import Dict, Any, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_whatsapp_service
from app.services.whatsapp import WhatsAppService
from app.services.rag import RAGService
from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


#@router.post("/whatsapp")
@router.post("")
async def whatsapp_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    whatsapp_service: WhatsAppService = Depends(get_whatsapp_service),
    db: Session = Depends(get_db),
):
    """
    Webhook para receber eventos do serviço WhatsApp
    """
    try:
        data = await request.json()
        logger.info(f"Webhook recebido: {data}")
        
        # Verificar se é uma mensagem
        if data.get("event_type") == "*events.Message":
            # Processar mensagem em background
            background_tasks.add_task(
                process_whatsapp_message,
                data,
                whatsapp_service,
                db
            )
        
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Erro ao processar webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def process_whatsapp_message(data: Dict[str, Any], whatsapp_service: WhatsAppService, db: Session):
    """
    Processa mensagens recebidas do WhatsApp
    """
    try:
        # Extrair informações da mensagem
        device_id = data.get("device_id")
        tenant_id = data.get("tenant_id")
        event = data.get("event", {})
        
        # Ignorar mensagens enviadas pelo próprio dispositivo
        if event.get("Info", {}).get("IsFromMe"):
            return
        
        # Extrair informações da mensagem
        sender = event.get("Info", {}).get("Sender", {}).get("User")
        chat_jid = event.get("Info", {}).get("Chat")
        message_content = event.get("Message", {}).get("Conversation")
        
        if not message_content:
            # Tentar extrair de outros tipos de mensagem
            if ext_text := event.get("Message", {}).get("ExtendedTextMessage", {}):
                message_content = ext_text.get("Text", "")
        
        if not message_content:
            # Ignorar mensagens sem conteúdo de texto
            return
        
        # Inicializar serviço RAG com o tenant_id correto
        rag_service = RAGService(tenant_id=tenant_id)
        
        # Tentar detectar a categoria baseado no conteúdo
        category = detect_category(message_content)
        
        # Verificar se é uma pergunta ou comando
        if message_content.strip().endswith("?") or is_command(message_content):
            # Obter contexto usando RAG, filtrando por categoria se detectada
            context = await rag_service.get_context(message_content, category=category)
            
            # Gerar resposta
            answer = await rag_service.get_answer(message_content, context)
            
            if answer:
                # Enviar resposta via WhatsApp
                await whatsapp_service.send_message(
                    device_id=device_id,
                    to=chat_jid,
                    message=answer
                )
                logger.info(f"Resposta enviada para {chat_jid}: {answer[:50]}...")
        
    except Exception as e:
        logger.error(f"Erro ao processar mensagem do WhatsApp: {e}")


def detect_category(text: str) -> Optional[str]:
    """
    Detecta a categoria mais provável com base no conteúdo da mensagem
    """
    # Categorias possíveis
    categories = {
        "atendimento": ["atendimento", "recepção", "ajuda", "suporte", "dúvida"],
        "consultas": ["agendar", "consulta", "horário", "marcar", "reagendar", "desmarca"],
        "procedimentos": ["procedimento", "tratamento", "canal", "extração", "limpeza", "clareamento"],
        "preços": ["preço", "valor", "custo", "orçamento", "pagamento", "parcela"],
        "urgência": ["dor", "urgente", "emergência", "sangramento", "acidente"]
    }
    
    text_lower = text.lower()
    
    # Pontuação para cada categoria
    scores = {category: 0 for category in categories}
    
    # Calcular pontuação
    for category, keywords in categories.items():
        for keyword in keywords:
            if keyword in text_lower:
                scores[category] += 1
    
    # Encontrar categoria com maior pontuação
    best_category = max(scores.items(), key=lambda x: x[1])
    
    # Retornar a categoria com maior pontuação, se tiver alguma ocorrência
    if best_category[1] > 0:
        return best_category[0]
    
    return None


def is_command(text: str) -> bool:
    """
    Verifica se o texto é um comando para o assistente
    """
    commands = ["agendar", "consulta", "horário", "horarios", "preço", 
                "valor", "ajuda", "info", "informação", "marcar"]
    
    lower_text = text.lower()
    
    # Verificar se o texto começa com algum dos comandos
    for command in commands:
        if lower_text.startswith(command) or f" {command} " in f" {lower_text} ":
            return True
    
    return False