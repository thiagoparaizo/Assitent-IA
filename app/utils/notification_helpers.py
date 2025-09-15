# app/utils/notification_helpers.py
"""
Helpers para facilitar o uso do sistema de notificações
"""

from datetime import datetime
from typing import Dict, Any, List, Optional
from app.services.notification import NotificationService, NotificationLevel
from app.utils.email_templates import EmailTemplates

class NotificationHelper:
    """Helper para simplificar envio de notificações padronizadas"""
    
    def __init__(self, notification_service: NotificationService):
        self.service = notification_service
        self.templates = EmailTemplates()
    
    async def send_whatsapp_reauth_alert(
        self,
        tenant_id: int,
        tenant_name: str,
        device_id: int,
        device_name: str,
        target_email: str,
        qr_code_url: Optional[str] = None
    ) -> bool:
        """Envia alerta de reautenticação padronizado"""
        
        template = self.templates.get_whatsapp_reauth_template()
        
        details = {
            "Tenant": f"{tenant_name} (ID: {tenant_id})",
            "Dispositivo": f"{device_name} (ID: {device_id})",
            "Status": "Reautenticação Necessária"
        }
        
        if qr_code_url:
            details["Link do QR Code"] = qr_code_url
        
        return await self.service.send_whatsapp_alert(
            alert_type="whatsapp_reauth",
            tenant_id=tenant_id,
            tenant_name=tenant_name,
            device_id=device_id,
            device_name=device_name,
            level=template["level"],
            message=template["message"],
            channel="email",
            target=target_email,
            custom_subject=f"⚠️ {template['title']} - {device_name}",
            suggested_action=template["suggested_action"],
            details=details
        )
    
    async def send_critical_update_alert(
        self,
        tenant_id: int,
        tenant_name: str,
        device_id: int,
        device_name: str,
        target_emails: List[str],
        current_version: str,
        required_version: str
    ) -> bool:
        """Envia alerta de atualização crítica para múltiplos emails"""
        
        template = self.templates.get_whatsapp_critical_update_template()
        
        details = {
            "Tenant": f"{tenant_name} (ID: {tenant_id})",
            "Dispositivo": f"{device_name} (ID: {device_id})",
            "Versão Atual": current_version,
            "Versão Necessária": required_version,
            "Criticidade": "ALTA - Ação Imediata Necessária"
        }
        
        success_count = 0
        for email in target_emails:
            success = await self.service.send_whatsapp_alert(
                alert_type="whatsapp_critical_update",
                tenant_id=tenant_id,
                tenant_name=tenant_name,
                device_id=device_id,
                device_name=device_name,
                level=template["level"],
                message=template["message"],
                channel="email",
                target=email,
                custom_subject=f"🚨 URGENTE: {template['title']} - {tenant_name}",
                suggested_action=template["suggested_action"],
                details=details
            )
            if success:
                success_count += 1
        
        return success_count > 0
    
    async def send_webhook_failure_alert(
        self,
        tenant_id: int,
        tenant_name: str,
        webhook_url: str,
        error_details: str,
        admin_emails: List[str],
        failure_count: int = 1
    ) -> bool:
        """Envia alerta de falha de webhook"""
        
        template = self.templates.get_webhook_failure_template()
        
        details = {
            "Tenant": f"{tenant_name} (ID: {tenant_id})",
            "URL do Webhook": webhook_url,
            "Falhas Consecutivas": str(failure_count),
            "Último Erro": error_details,
            "Timestamp": datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        }
        
        success_count = 0
        for email in admin_emails:
            success = await self.service.send_whatsapp_alert(
                alert_type="webhook_failure",
                tenant_id=tenant_id,
                tenant_name=tenant_name,
                device_id=0,  # Não específico de dispositivo
                device_name="Sistema",
                level=template["level"],
                message=template["message"],
                channel="email",
                target=email,
                custom_subject=f"❌ {template['title']} - {tenant_name}",
                suggested_action=template["suggested_action"],
                details=details
            )
            if success:
                success_count += 1
        
        return success_count > 0
    
    async def send_token_critical_alert(
        self,
        alert,
        tenant_name: str,
        agent_name: str,
        admin_emails: List[str]
    ) -> bool:
        """Envia alerta crítico de tokens"""
        
        template = self.templates.get_token_limit_critical_template()
        percentage = (alert.current_usage / alert.max_limit) * 100 if alert.max_limit > 0 else 0
        
        # Usar o método existente do service com template customizado
        success_count = 0
        for email in admin_emails:
            success = await self.service.send_token_usage_alert(
                alert=alert,
                channel="email",
                target=email
            )
            if success:
                success_count += 1
        
        return success_count > 0