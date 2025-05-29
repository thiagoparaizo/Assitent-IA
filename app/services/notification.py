# app/services/notification.py
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import httpx
from typing import Any, Dict, Optional
import json
import logging

from app.core.config import settings

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("app.services.notification")

class NotificationService:
    """Serviço para envio de notificações por diferentes canais."""
    
    def __init__(self, db_session=None):
        self.db = db_session
    
    async def send_token_usage_alert(
        self,
        alert,
        channel: str = "email",
        target: str = None
    ) -> bool:
        """Envia alerta de uso de tokens pelo canal especificado."""
        try:
            # Obter informações adicionais do tenant/agente
            tenant_name = "Unknown Tenant"
            agent_name = "Unknown Agent"
            
            if self.db:
                if alert.tenant_id:
                    from app.db.models.tenant import Tenant
                    tenant = self.db.query(Tenant).filter(Tenant.id == alert.tenant_id).first()
                    if tenant:
                        tenant_name = tenant.name
                
                if alert.agent_id:
                    from app.db.models.agent import Agent
                    agent = self.db.query(Agent).filter(Agent.id == alert.agent_id).first()
                    if agent:
                        agent_name = agent.name
            
            # Preparar conteúdo do alerta
            subject = f"Alerta de Uso de Tokens - {tenant_name}"
            
            # Determinar tipo de limite
            limit_type_desc = "mensal"
            if alert.limit_type == "daily":
                limit_type_desc = "diário"
            
            # Calcular uso percentual
            percentage = (alert.current_usage / alert.max_limit) * 100 if alert.max_limit > 0 else 0
            
            # Criar corpo da mensagem
            body = f"""
            <h2>Alerta de Uso de Tokens LLM</h2>
            
            <p>Este é um alerta automático para informar que o uso de tokens LLM atingiu {percentage:.1f}% do limite {limit_type_desc}.</p>
            
            <h3>Detalhes:</h3>
            <ul>
                <li><strong>Tenant:</strong> {tenant_name} (ID: {alert.tenant_id})</li>
                {"<li><strong>Agente:</strong> " + agent_name + " (ID: " + str(alert.agent_id) + ")</li>" if alert.agent_id else ""}
                <li><strong>Uso Atual:</strong> {alert.current_usage:,} tokens</li>
                <li><strong>Limite {limit_type_desc.capitalize()}:</strong> {alert.max_limit:,} tokens</li>
                <li><strong>Percentual Utilizado:</strong> {percentage:.1f}%</li>
                <li><strong>Data do Alerta:</strong> {alert.created_at.strftime('%d/%m/%Y %H:%M:%S')}</li>
            </ul>
            
            <p>Acesse o painel administrativo para mais detalhes e ajustar limites se necessário.</p>
            """
            
            # Enviar notificação pelo canal apropriado
            if channel == "email" and target:
                return await self._send_email(target, subject, body)
            elif channel == "webhook" and target:
                webhook_payload = {
                    "type": "token_usage_alert",
                    "tenant_id": alert.tenant_id,
                    "tenant_name": tenant_name,
                    "agent_id": str(alert.agent_id) if alert.agent_id else None,
                    "agent_name": agent_name if alert.agent_id else None,
                    "limit_type": alert.limit_type,
                    "current_usage": alert.current_usage,
                    "max_limit": alert.max_limit,
                    "percentage": percentage,
                    "timestamp": alert.created_at.isoformat()
                }
                return await self._send_webhook(target, webhook_payload)
            
            return False
            
        except Exception as e:
            logger.error(f"Error sending token usage alert: {e}")
            return False
    
    async def _send_email(self, to_email: str, subject: str, body: str) -> bool:
        """Envia notificação por email."""
        try:
            # Configuração de email
            from_email = settings.EMAIL_FROM or "no-reply@yourdomain.com"
            smtp_server = settings.SMTP_SERVER or "smtp.gmail.com"
            smtp_port = settings.SMTP_PORT or 587
            smtp_user = settings.SMTP_USER
            smtp_password = settings.SMTP_PASSWORD
            
            
            # Criar mensagem
            message = MIMEMultipart()
            message["From"] = from_email
            message["To"] = to_email
            message["Subject"] = subject
            
            # Adicionar corpo HTML
            message.attach(MIMEText(body, "html"))
            
            # Enviar email
            async with aiosmtplib.SMTP(hostname=smtp_server, port=smtp_port, start_tls=settings.SMTP_TLS) as smtp:
                await smtp.login(smtp_user, smtp_password)
                await smtp.send_message(message)
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending email notification: {e}")
            return False
    
    async def _send_webhook(self, webhook_url: str, payload: Dict[str, Any]) -> bool:
        """Envia notificação por webhook."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=10.0
                )
                
                response.raise_for_status()
                return True
                
        except Exception as e:
            logger.error(f"Error sending webhook notification: {e}")
            return False