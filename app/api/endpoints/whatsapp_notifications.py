# app/api/endpoints/whatsapp_notifications.py
# Versão atualizada com integração aos novos templates HTML

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

@router.post("/notificar_saude_dispositivos")
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
        
        # Processar cada tipo de notificação
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
    """
    device_id = notification_data["device_id"]
    device_name = notification_data["device_name"]
    tenant_id = notification_data["tenant_id"]
    
    admin_emails = await get_admin_emails_for_tenant(tenant_id)
    
    details = {
        "Dispositivo": f"{device_name} (ID: {device_id})",
        "Tenant": f"{tenant_name} (ID: {tenant_id})",
        "Problema": "Cliente WhatsApp desatualizado",
        "Criticidade": "ALTA - Ação Imediata Necessária",
        "Impacto": "Todos os dispositivos podem parar de funcionar"
    }
    
    message = """Foi detectado que o cliente WhatsApp está usando uma versão desatualizada e foi rejeitado pelo WhatsApp.
    
    <strong>Este é um problema crítico que requer ação imediata para evitar interrupção total do serviço.</strong>"""
    
    suggested_action = """AÇÃO IMEDIATA NECESSÁRIA:
    
    1. Atualizar biblioteca whatsmeow para a versão mais recente
    2. Recompilar e reiniciar o serviço WhatsApp
    3. Reconectar todos os dispositivos afetados
    4. Verificar se todos os tenants foram impactados
    
    ⚠️ Sem essa atualização, TODOS os dispositivos podem parar de funcionar permanentemente."""
    
    for email in admin_emails:
        success = await notification_service.send_whatsapp_alert(
            alert_type="whatsapp_critical_update",
            tenant_id=tenant_id,
            tenant_name=tenant_name,
            device_id=device_id,
            device_name=device_name,
            level="critical",
            message=message,
            channel="email",
            target=email,
            custom_subject="🚨 URGENTE: Cliente WhatsApp Desatualizado - Ação Imediata Necessária",
            suggested_action=suggested_action,
            details=details
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
    """
    device_id = notification_data["device_id"]
    device_name = notification_data["device_name"]
    tenant_id = notification_data["tenant_id"]
    
    tenant_contacts = await get_tenant_notification_contacts(tenant_id)
    
    details = {
        "Dispositivo": f"{device_name} (ID: {device_id})",
        "Tenant": f"{tenant_name} (ID: {tenant_id})",
        "Problema": notification_data.get('message', 'Erro de conexão detectado'),
        "Status": "Tentando reconectar automaticamente",
        "Próximos Passos": "Monitoramento automático ativo"
    }
    
    message = """Detectamos um problema de conexão com seu dispositivo WhatsApp.
    
    <strong>Não se preocupe:</strong> Estamos tentando reconectar automaticamente e monitorando a situação de perto."""
    
    suggested_action = """O que estamos fazendo:
    • Tentativas automáticas de reconexão a cada 30 segundos
    • Monitoramento contínuo do status de conectividade
    • Logs detalhados para análise técnica
    
    O que você pode fazer:
    • Verificar se sua internet está estável
    • Aguardar alguns minutos para reconexão automática
    • Se o problema persistir por mais de 10 minutos, pode ser necessário reautenticar
    
    Entraremos em contato se precisarmos de ações adicionais de sua parte."""
    
    for contact in tenant_contacts:
        if contact.get("email"):
            await notification_service.send_whatsapp_alert(
                alert_type="whatsapp_connection",
                tenant_id=tenant_id,
                tenant_name=tenant_name,
                device_id=device_id,
                device_name=device_name,
                level="warning",
                message=message,
                channel="email",
                target=contact["email"],
                custom_subject=f"⚠️ Problema de Conexão Detectado - {device_name}",
                suggested_action=suggested_action,
                details=details
            )

async def handle_reauth_required_notification(
    notification_data: Dict[str, Any], 
    tenant_name: str, 
    notification_service: NotificationService
):
    """
    Trata notificações de reautenticação necessária
    """
    device_id = notification_data["device_id"]
    device_name = notification_data["device_name"]
    tenant_id = notification_data["tenant_id"]
    
    tenant_contacts = await get_tenant_notification_contacts(tenant_id)
    
    details = {
        "Dispositivo": f"{device_name} (ID: {device_id})",
        "Tenant": f"{tenant_name} (ID: {tenant_id})",
        "Ação Necessária": "Reautenticação via QR Code",
        "Tempo Estimado": "2-3 minutos",
        "Link Direto": f"{URL_PAINEL}/whatsapp/devices/{device_id}"
    }
    
    message = """Seu dispositivo WhatsApp precisa ser reautenticado para continuar funcionando normalmente.
    
    <strong>Este é um procedimento de segurança normal</strong> que acontece periodicamente para manter a conexão segura."""
    
    suggested_action = f"""Para reativar seu dispositivo:
    
    1. <strong>Acesse o painel:</strong> {URL_PAINEL}/whatsapp/devices/{device_id}
    2. <strong>Clique em "Reconectar"</strong> no dispositivo {device_name}
    3. <strong>Escaneie o QR Code</strong> com o WhatsApp do seu celular
    4. <strong>Aguarde a confirmação</strong> de conexão
    
    📱 <strong>Como escanear:</strong>
    • Abra o WhatsApp no seu celular
    • Vá em Configurações > Aparelhos conectados
    • Toque em "Conectar um aparelho"
    • Aponte a câmera para o QR Code
    
    Se precisar de ajuda, nossa equipe está disponível para auxiliar."""
    
    for contact in tenant_contacts:
        if contact.get("email"):
            success = await notification_service.send_whatsapp_alert(
                alert_type="whatsapp_reauth",
                tenant_id=tenant_id,
                tenant_name=tenant_name,
                device_id=device_id,
                device_name=device_name,
                level="warning",
                message=message,
                channel="email",
                target=contact["email"],
                custom_subject=f"🔐 Reautenticação Necessária - {device_name}",
                suggested_action=suggested_action,
                details=details
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
    """
    device_id = notification_data["device_id"]
    tenant_id = notification_data["tenant_id"]
    device_name = notification_data.get("device_name", "Sistema")
    
    details_data = notification_data.get("details", {})
    consecutive_failures = details_data.get("consecutive_failures", 0)
    webhook_url = details_data.get("webhook_url", "")
    last_error = details_data.get("last_error", "Timeout de conexão")
    
    if consecutive_failures >= 5:
        admin_emails = await get_admin_emails_for_tenant(tenant_id)
        
        details = {
            "Tenant": f"{tenant_name} (ID: {tenant_id})",
            "Webhook URL": webhook_url,
            "Falhas Consecutivas": str(consecutive_failures),
            "Último Erro": last_error,
            "Impacto": "Notificações podem não estar sendo entregues",
            "Status": "Webhook temporariamente desabilitado"
        }
        
        message = """O webhook configurado está falhando consistentemente e pode estar impactando a entrega de notificações.
        
        <strong>Ação necessária:</strong> Verificação e correção da configuração do webhook para restaurar as notificações."""
        
        suggested_action = """Verificações necessárias:
        
        1. <strong>Conectividade:</strong> URL do webhook está acessível?
        2. <strong>Servidor:</strong> Aplicação de destino está respondendo?
        3. <strong>Autenticação:</strong> Credenciais estão corretas?
        4. <strong>Firewall:</strong> Portas necessárias estão abertas?
        5. <strong>SSL:</strong> Certificados estão válidos?
        
        <strong>Ações recomendadas:</strong>
        • Testar manualmente a URL do webhook
        • Verificar logs do servidor de destino
        • Considerar desabilitar temporariamente se o problema persistir
        • Configurar webhook alternativo se necessário"""
        
        for email in admin_emails:
            await notification_service.send_whatsapp_alert(
                alert_type="webhook_failure",
                tenant_id=tenant_id,
                tenant_name=tenant_name,
                device_id=device_id,
                device_name=device_name,
                level="error",
                message=message,
                channel="email",
                target=email,
                custom_subject=f"🔗 Falha Crítica de Webhook - {tenant_name}",
                suggested_action=suggested_action,
                details=details,
                error_code=f"WEBHOOK_FAIL_{consecutive_failures}"
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
    
    # Para desconexões, apenas logar - reconexão automática é tentada
    logger.info(f"Dispositivo {device_name} (ID: {device_id}) do tenant {tenant_name} (ID: {tenant_id}) desconectado")
    
    # Notificar apenas se a desconexão persistir (isso seria implementado com delay)
    # Por enquanto, apenas log

async def handle_generic_notification(
    notification_data: Dict[str, Any], 
    tenant_name: str, 
    notification_service: NotificationService
):
    """
    Trata notificações genéricas
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
        
        details = {
            "Dispositivo": f"{device_name} (ID: {device_id})",
            "Tenant": f"{tenant_name} (ID: {tenant_id})",
            "Tipo de Alerta": title,
            "Nível": level.upper(),
            "Timestamp": notification_data.get("timestamp", datetime.now().isoformat())
        }
        
        formatted_message = f"""<strong>{title}</strong>
        
        {message}"""
        
        suggested_action = notification_data.get("suggested_action", 
            "Verifique os logs do sistema e entre em contato com o suporte técnico se necessário.")
        
        for email in admin_emails:
            await notification_service.send_whatsapp_alert(
                alert_type="whatsapp_generic",
                tenant_id=tenant_id,
                tenant_name=tenant_name,
                device_id=device_id,
                device_name=device_name,
                level=level,
                message=formatted_message,
                channel="email",
                target=email,
                custom_subject=f"🔔 [{level.upper()}] WhatsApp - {title}",
                suggested_action=suggested_action,
                details=details
            )

async def send_critical_alert_to_admins(
    notification_data: Dict[str, Any], 
    tenant_name: str, 
    notification_service: NotificationService
):
    """
    Envia alertas críticos para administradores do sistema
    """
    system_admin_emails = await get_system_admin_emails()
    
    device_id = notification_data["device_id"]
    device_name = notification_data["device_name"]
    tenant_id = notification_data["tenant_id"]
    
    details = {
        "Tenant": f"{tenant_name} (ID: {tenant_id})",
        "Dispositivo": f"{device_name} (ID: {device_id})",
        "Tipo de Alerta": notification_data.get("type", "unknown"),
        "Nível": "CRITICAL",
        "Código de Erro": notification_data.get("error_code", "N/A"),
        "Timestamp": notification_data.get("timestamp", datetime.now().isoformat())
    }
    
    message = f"""<strong>ALERTA CRÍTICO detectado no sistema WhatsApp</strong>
    
    Um problema crítico foi identificado e requer atenção imediata da equipe técnica.
    
    <strong>Detalhes:</strong> {notification_data.get('message', 'Erro crítico não especificado')}"""
    
    suggested_action = f"""{notification_data.get('suggested_action', 'Verificar logs e status do sistema')}
    
    <strong>Ações imediatas recomendadas:</strong>
    • Verificar logs detalhados do sistema
    • Avaliar impacto em outros tenants
    • Preparar comunicação para clientes se necessário
    • Considerar acionamento de protocolo de emergência"""
    
    for email in system_admin_emails:
        success = await notification_service.send_whatsapp_alert(
            alert_type="system_critical",
            tenant_id=tenant_id,
            tenant_name=tenant_name,
            device_id=device_id,
            device_name=device_name,
            level="critical",
            message=message,
            channel="email",
            target=email,
            custom_subject="🚨 ALERTA CRÍTICO - Sistema WhatsApp - Ação Imediata Necessária",
            suggested_action=suggested_action,
            details=details,
            error_code=notification_data.get("error_code")
        )
        
        if success:
            logger.info(f"Alerta crítico enviado para {email}")
        else:
            logger.error(f"Erro ao enviar alerta crítico para {email}")

# Funções auxiliares (mantidas inalteradas)

async def get_tenant_info(tenant_id: int, db: Session) -> Dict[str, Any]:
    """Busca informações do tenant"""
    try:
        from app.db.models.tenant import Tenant
        from sqlalchemy import select
        
        query = select(Tenant).where(Tenant.id == tenant_id)
        result = db.execute(query)
        if result:
            tenant = result.scalar_one_or_none()
            if tenant:
                return {"name": tenant.name, "description": tenant.description}
        
    except Exception as e:
        logger.error(f"Erro ao buscar info do tenant {tenant_id}: {e}")
    
    return {}

async def get_tenant_notification_contacts(tenant_id: int) -> list:
    """Busca contatos de notificação do tenant"""
    try:
        # TODO: Implementar busca de contatos do tenant
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
        # TODO: Implementar busca de admins responsáveis
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
        # TODO: Implementar integração com sistema de tickets
        logger.info(f"Ticket criado: {ticket_data['title']}")
    except Exception as e:
        logger.error(f"Erro ao criar ticket interno: {e}")