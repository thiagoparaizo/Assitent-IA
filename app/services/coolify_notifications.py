# app/integrations/coolify_notifications.py
"""
Integração específica com Coolify para notificações de deploy e health
"""

from datetime import datetime
from typing import Dict, Any
from app.services.notification import NotificationService, NotificationLevel

class CoolifyNotificationIntegration:
    """Integração com Coolify para notificações automáticas"""
    
    def __init__(self, notification_service: NotificationService):
        self.service = notification_service
    
    async def send_deploy_success_notification(
        self,
        app_name: str,
        version: str,
        deployment_time: str,
        admin_emails: list
    ) -> bool:
        """Notifica sobre deploy bem-sucedido"""
        
        details = {
            "Aplicação": app_name,
            "Versão": version,
            "Tempo de Deploy": deployment_time,
            "Status": "✅ Sucesso",
            "Health Check": "Passou em todas as verificações"
        }
        
        success_count = 0
        for email in admin_emails:
            success = await self.service.send_health_check_alert(
                service_name=app_name,
                status="healthy",
                failed_checks=[],
                details=details,
                target=email,
                suggested_actions=["Monitorar logs pós-deploy", "Verificar métricas de performance"]
            )
            if success:
                success_count += 1
        
        return success_count > 0
    
    async def send_deploy_failure_notification(
        self,
        app_name: str,
        version: str,
        error_message: str,
        admin_emails: list
    ) -> bool:
        """Notifica sobre falha no deploy"""
        
        import pytz
        fortaleza_tz = pytz.timezone('America/Fortaleza')
        agora_fortaleza = datetime.now(fortaleza_tz)
        data_hora_formatada = agora_fortaleza.strftime('%d/%m/%Y às %H:%M:%S')
        
        details = {
            "Aplicação": app_name,
            "Versão": version,
            "Status": "❌ Falha",
            "Erro": error_message,
            "Timestamp": data_hora_formatada
        }
        
        success_count = 0
        for email in admin_emails:
            success = await self.service.send_health_check_alert(
                service_name=app_name,
                status="unhealthy",
                failed_checks=["Deploy failed", "Application not responding"],
                details=details,
                target=email,
                suggested_actions=[
                    "Verificar logs de deploy no Coolify",
                    "Validar configurações de ambiente",
                    "Considerar rollback para versão anterior"
                ]
            )
            if success:
                success_count += 1
        
        return success_count > 0