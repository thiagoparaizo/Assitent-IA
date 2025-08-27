# ==============================================
# NOVO ARQUIVO: app/api/endpoints/whatsapp_notifications.py
# ==============================================

from datetime import datetime
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
import logging
from app.api.deps import get_db

from app.services.notification import NotificationService

logger = logging.getLogger('app.api.endpoints.whatsapp_notifications')
logging.basicConfig(level=logging.DEBUG)

router = APIRouter()

URL_PAINEL = "http://assistente-web-admin.iazera.cloud"

class WhatsAppDeviceNotification(BaseModel):
    device_id: int
    device_name: str
    tenant_id: int
    level: str  # info, warning, error, critical
    type: str
    title: str
    message: str
    timestamp: datetime
    details: Dict[str, Any] = Field(default_factory=dict)
    error_code: str = None
    suggested_action: str = None

@router.post("/whatsapp-notifications")
async def receive_whatsapp_notification(
    notification: WhatsAppDeviceNotification,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Recebe notificações do serviço WhatsApp sobre problemas de dispositivos
    """
    try:
        logger.info(f"Recebida notificação WhatsApp: {notification.type} para dispositivo {notification.device_id}")
        
        # Processar notificação em background
        background_tasks.add_task(
            process_whatsapp_notification,
            notification.dict(),
            db
        )
        
        return {"status": "received", "message": "Notificação processada"}
        
    except Exception as e:
        logger.error(f"Erro ao processar notificação WhatsApp: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def process_whatsapp_notification(notification_data: Dict[str, Any], db: Session):
    """
    Processa a notificação do WhatsApp em background
    
    """
    try:
        notification_service = NotificationService(db)
        
        # Determinar ações baseadas no tipo de notificação
        notification_type = notification_data.get("type")
        level = notification_data.get("level")
        device_id = notification_data.get("device_id")
        tenant_id = notification_data.get("tenant_id")
        device_name = notification_data.get("device_name", f"Device {device_id}")
        
        # Buscar informações do tenant para personalizar notificação
        tenant_info = await get_tenant_info(tenant_id, db)
        tenant_name = tenant_info.get("name", f"Tenant {tenant_id}") if tenant_info else f"Tenant {tenant_id}"
        
        # USAR send_whatsapp_alert para cada tipo de notificação
        if notification_type == "client_outdated":
            await handle_client_outdated_notification(
                notification_data, tenant_name, notification_service
            )
        elif notification_type == "device_connection_error":
            await handle_connection_error_notification(
                notification_data, tenant_name, notification_service
            )
        elif notification_type == "device_requires_reauth":
            await handle_reauth_required_notification(
                notification_data, tenant_name, notification_service
            )
        elif notification_type == "webhook_delivery_failure":
            await handle_webhook_failure_notification(
                notification_data, tenant_name, notification_service
            )
        elif notification_type == "device_disconnected":
            await handle_device_disconnected_notification(
                notification_data, tenant_name, notification_service
            )
        else:
            # Notificação genérica
            await handle_generic_notification(
                notification_data, tenant_name, notification_service
            )
            
        # Sempre enviar notificação geral para admins se for crítico
        if level == "critical":
            await send_critical_alert_to_admins(notification_data, tenant_name, notification_service)
            
        logger.info(f"Notificação WhatsApp processada: {notification_type} para dispositivo {device_id}")
        
    except Exception as e:
        logger.error(f"Erro ao processar notificação WhatsApp em background: {e}")

async def handle_client_outdated_notification(
    notification_data: Dict[str, Any], 
    tenant_name: str, 
    notification_service: NotificationService
):
    """
    Trata notificações de cliente desatualizado - CRÍTICO
    USA send_whatsapp_alert para admins técnicos
    """
    device_id = notification_data["device_id"]
    device_name = notification_data["device_name"]
    tenant_id = notification_data["tenant_id"]
    # Buscar contatos de administração técnica
    admin_emails = await get_admin_emails_for_tenant(tenant_id)
    
    message=f"""🚨🚨 AÇÃO URGENTE NECESSÁRIA 🚨🚨 - Cliente WhatsApp Desatualizado
            
Dispositivo: {device_name} (ID: {device_id})
Tenant: {tenant_name}

O cliente WhatsApp está usando uma versão desatualizada e foi rejeitado pelo WhatsApp.

AÇÃO IMEDIATA NECESSÁRIA:
1. Atualizar biblioteca whatsmeow para a versão mais recente
2. Recompilar e reiniciar o serviço WhatsApp
3. Reconectar todos os dispositivos afetados

⚠️⚠️ Sem essa atualização, TODOS os dispositivos podem parar de funcionar.⚠️⚠️""",
            
        
    
     # USAR send_whatsapp_alert para cada admin
    for email in admin_emails:
        success = await notification_service.send_whatsapp_alert(
            alert_type="whatsapp_critical",
            tenant_id=tenant_id,
            tenant_name=tenant_name,
            device_id=device_id,
            device_name=device_name,
            level="critical",
            message=message,
            channel="email",
            target=email,
            custom_subject="🚨 URGENTE: Cliente WhatsApp Desatualizado",
        )
        
        if success:
            logger.info(f"Alerta crítico enviado para {email}")
        else:
            logger.error(f"Falha ao enviar alerta crítico para {email}")
    
    # Criar ticket interno se sistema de tickets estiver integrado
    await create_internal_ticket({
        "title": f"URGENTE: Cliente WhatsApp desatualizado - {tenant_name}",
        "description": message,
        "priority": "critical",
        "category": "whatsapp_infrastructure",
        "tenant_id": tenant_id,
        "assigned_team": "infrastructure"
    })

async def handle_connection_error_notification(
    notification_data: Dict[str, Any], 
    tenant_name: str, 
    notification_service: NotificationService
):
    """
    Trata erros de conexão de dispositivos
    USA send_whatsapp_alert para notificar o tenant
    """
    device_id = notification_data["device_id"]
    device_name = notification_data["device_name"]
    tenant_id = notification_data["tenant_id"]
    
    tenant_contacts = await get_tenant_notification_contacts(tenant_id)
    
    for contact in tenant_contacts:
        if contact.get("email"):
            await notification_service.send_whatsapp_alert(
                alert_type="whatsapp_connection",
                tenant_id=tenant_id,
                tenant_name=tenant_name,
                device_id=device_id,
                device_name=device_name,
                level="error",
                message=f"""❌ Problema de Conexão - WhatsApp

Dispositivo: {device_name}
Problema: {notification_data.get('message', 'Erro de conexão detectado')}

O que estamos fazendo:
• Tentando reconectar automaticamente
• Monitorando a situação

O que você pode fazer:
• Verificar se seu dispositivo está conectado à internet
• Se o problema persistir, pode ser necessário reautenticar o dispositivo

Entraremos em contato se precisarmos de ações adicionais.""",
                channel="email",
                target=contact["email"],
                custom_subject=f"Problema de Conexão - {device_name}",
            )


async def handle_reauth_required_notification(
    notification_data: Dict[str, Any], 
    tenant_name: str, 
    notification_service: NotificationService
):
    """
    Trata notificações de reautenticação necessária
    USA send_whatsapp_alert para contatos do tenant
    """
    device_id = notification_data["device_id"]
    device_name = notification_data["device_name"]
    tenant_id = notification_data["tenant_id"]
    
    # Buscar contatos do tenant
    tenant_contacts = await get_tenant_notification_contacts(tenant_id)
    
    # USAR send_whatsapp_alert para cada contato
    for contact in tenant_contacts:
        if contact.get("email"):
            success = await notification_service.send_whatsapp_alert(
                alert_type="whatsapp_reauth",
                tenant_id=tenant_id,
                tenant_name=tenant_name,
                device_id=device_id,
                device_name=device_name,
                level="warning",
                message=f"""⚠️ Reautenticação Necessária - WhatsApp

Olá,
    
    Seu dispositivo WhatsApp precisa ser reautenticado:
    
    Dispositivo: {device_name}
    
    Para reativar o dispositivo:
    1. Acesse o painel de controle
    2. Vá para a seção WhatsApp
    3. Clique em "Reconectar" no dispositivo {device_name}
    4. Use o WhatsApp no seu celular para escanear o novo QR Code
    
    Link direto: {URL_PAINEL}/whatsapp/devices/{device_id}
    
    Se precisar de ajuda, entre em contato conosco.
    
    Equipe Técnica
    {URL_PAINEL}""",
                channel="email",
                target=contact["email"],
                custom_subject=f"Reautenticação Necessária - {device_name}",
            )
            
            if success:
                logger.info(f"Alerta de reauth enviado para {contact['email']}")
            else:
                logger.error(f"Falha ao enviar alerta de reauth para {contact['email']}")

async def handle_webhook_failure_notification(
    notification_data: Dict[str, Any], 
    tenant_name: str, 
    notification_service: NotificationService
):
    """
    Trata falhas consecutivas de webhook
    USA send_whatsapp_alert para admins técnicos
    """
    device_id = notification_data["device_id"]
    tenant_id = notification_data["tenant_id"]
    
    details = notification_data.get("details", {})
    consecutive_failures = details.get("consecutive_failures", 0)
    webhook_url = details.get("webhook_url", "")
    
    if consecutive_failures >= 5:
        admin_emails = await get_admin_emails_for_tenant(tenant_id)
        
        for email in admin_emails:
            await notification_service.send_whatsapp_alert(
                alert_type="whatsapp_webhook",
                tenant_id=tenant_id,
                tenant_name=tenant_name,
                device_id=device_id,
                device_name=notification_data.get("device_name", "N/A"),
                level="error",
                message=f"""🔗 Falha Crítica de Webhook - WhatsApp

Tenant: {tenant_name}
Webhook: {webhook_url}
Falhas Consecutivas: {consecutive_failures}

O webhook configurado está falhando consistentemente.

Verificações necessárias:
1. URL do webhook está acessível?
2. Servidor de destino está respondendo?
3. Configuração de autenticação está correta?

Considere desabilitar o webhook temporariamente se o problema persistir.""",
                channel="email",
                target=email,
                custom_subject=f"Falha Crítica de Webhook - {tenant_name}",
            )

async def handle_device_disconnected_notification(
    notification_data: Dict[str, Any], 
    tenant_name: str, 
    notification_service: NotificationService
):
    """
    Trata notificações de dispositivo desconectado
    """
    device_id = notification_data["device_id"]
    tenant_id = notification_data["tenant_id"]
    device_name = notification_data["device_name"]
    # Para desconexões, apenas logar e aguardar reconexão automática
    # Só notificar se a desconexão persistir por muito tempo
    logger.info(f"Dispositivo {device_name} (ID: {device_id}) do tenant {tenant_name} (ID: {tenant_id}) desconectado")
    pass

async def handle_generic_notification(
    notification_data: Dict[str, Any], 
    tenant_name: str, 
    notification_service: NotificationService
):
    """
    Trata notificações genéricas
    USA send_whatsapp_alert de forma genérica
    """
    device_id = notification_data["device_id"]
    device_name = notification_data["device_name"]
    tenant_id = notification_data["tenant_id"]
    level = notification_data["level"]
    message = notification_data["message"]
    title = notification_data["title"]
    
    # Determinar quem deve receber baseado no nível
    if level in ["critical", "error"]:
        admin_emails = await get_admin_emails_for_tenant(tenant_id)
        
        for email in admin_emails:
            await notification_service.send_whatsapp_alert(
                alert_type="whatsapp_generic",
                tenant_id=tenant_id,
                tenant_name=tenant_name,
                device_id=device_id,
                device_name=device_name,
                level=level,
                message=f"{title}\n\n{message}",
                channel="email",
                target=email,
                custom_subject=f"[{level.upper()}] WhatsApp - {title}",
            )

async def send_critical_alert_to_admins(notification_data: Dict[str, Any], 
    tenant_name: str, 
    notification_service: NotificationService
):
    """
    Envia alertas críticos para administradores do sistema
    """
    system_admin_emails = await get_system_admin_emails()
    
    critical_message = f"""
    🚨 ALERTA CRÍTICO - Sistema WhatsApp
    
    Um problema crítico foi detectado no sistema WhatsApp:
    
    Tenant: {tenant_name} (ID: {notification_data['tenant_id']})
    Dispositivo: {notification_data['device_name']} (ID: {notification_data['device_id']})
    Tipo: {notification_data['alert_type']}
    Erro: {notification_data.get('error_code', 'N/A')}
    
    Detalhes: {notification_data['message']}
    
    Ação Sugerida: {notification_data.get('suggested_action', 'Verificar logs e status do sistema')}
    
    Timestamp: {notification_data['timestamp']}
    
    ⚠️ Este alerta requer atenção imediata da equipe técnica.
    """
    
    device_id = notification_data["device_id"]
    device_name = notification_data["device_name"]
    tenant_id = notification_data["tenant_id"]
    message = notification_data["message"]
    title = notification_data["title"]
    
    for email in system_admin_emails:
        
        success = await notification_service.send_whatsapp_alert(
            alert_type="whatsapp_critical",
            tenant_id=tenant_id,
            tenant_name=tenant_name,
            device_id=device_id,
            device_name=device_name,
            level="critical",
            message=message,
            channel="email",
            target=email,
            custom_subject="🚨 URGENTE: Erro Crítico",
        )
        
        if success:
            logger.info(f"Alerta crítico enviado para {email}")
        else:
            logger.error(f"Erro ao enviar alerta crítico para {email}")

# Funções auxiliares

async def get_tenant_info(tenant_id: int, db: Session) -> Dict[str, Any]:
    """Busca informações do tenant"""
    try:
        # Implementar busca no banco de dados
        # Exemplo simplificado:
        query = "SELECT name, contact_email FROM tenants WHERE id = %s"
        result = db.execute(query, (tenant_id,)).fetchone()
        if result:
            return {"name": result[0], "contact_email": result[1]}
    except Exception as e:
        logger.error(f"Erro ao buscar info do tenant {tenant_id}: {e}")
    
    return {}

async def get_tenant_notification_contacts(tenant_id: int) -> list:
    """Busca contatos de notificação do tenant"""
    try:
        # TODO Implementar busca de contatos do tenant
        # Pode incluir: email principal, contatos técnicos, etc.
        return [
            {"email": "thiago.paraizo@gmail.com", "type": "primary"},
            {"email": "homeparaizo@gmail.com", "type": "technical"}
        ]
    except Exception as e:
        logger.error(f"Erro ao buscar contatos do tenant {tenant_id}: {e}")
        return []

async def get_admin_emails_for_tenant(tenant_id: int) -> list:
    """Busca emails de administradores técnicos responsáveis pelo tenant"""
    try:
        # Implementar busca de admins responsáveis
        return ["thiagoparaizo@gmail.com"]
    except Exception as e:
        logger.error(f"Erro ao buscar admins do tenant {tenant_id}: {e}")
        return []

async def get_system_admin_emails() -> list:
    """Busca emails de administradores do sistema"""
    return ["thiagoparaizo@gmail.com"]

async def create_internal_ticket(ticket_data: Dict[str, Any]):
    """Cria ticket interno no sistema de suporte (se integrado)"""
    try:
        # Implementar integração com sistema de tickets
        # Ex: Jira, ServiceNow, etc.
        logger.info(f"Ticket criado: {ticket_data['title']}")
    except Exception as e:
        logger.error(f"Erro ao criar ticket interno: {e}")

