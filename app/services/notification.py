# app/services/notification.py - Versão corrigida com CSS limpo

from datetime import datetime
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import httpx
from typing import Any, Dict, Optional, List
import json
import logging
from enum import Enum

from app.core.config import settings

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("app.services.notification")

class NotificationLevel(str, Enum):
    """Níveis de notificação"""
    CRITICAL = "critical"
    ERROR = "error"  
    WARNING = "warning"
    INFO = "info"

class EmailTemplateBuilder:
    """Construtor de templates HTML para emails"""
    
    BASE_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{ 
            font-family: Arial, sans-serif; 
            line-height: 1.6; 
            color: #333; 
            margin: 0; 
            padding: 0; 
            background-color: #f5f5f5;
        }}
        .container {{ 
            max-width: 600px; 
            margin: 20px auto; 
            background-color: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .header {{ 
            background-color: {header_color}; 
            color: white; 
            padding: 30px 20px; 
            text-align: center;
        }}
        .header h1 {{
            margin: 0 0 10px 0;
            font-size: 24px;
            font-weight: 600;
        }}
        .header p {{
            margin: 0;
            opacity: 0.9;
            font-size: 16px;
        }}
        .content {{ 
            padding: 30px 20px; 
        }}
        .alert-level {{
            display: inline-block;
            padding: 6px 12px;
            border-radius: 4px;
            font-weight: bold;
            text-transform: uppercase;
            font-size: 12px;
            margin-bottom: 20px;
            background-color: {level_bg_color};
            color: {level_text_color};
        }}
        .message-box {{
            background-color: #f8f9fa;
            border-left: 4px solid {header_color};
            padding: 20px;
            margin: 20px 0;
            border-radius: 0 4px 4px 0;
        }}
        .details {{ 
            background-color: #fff; 
            border: 1px solid #e9ecef;
            border-radius: 6px; 
            margin: 20px 0; 
        }}
        .details-header {{
            background-color: #f8f9fa;
            padding: 15px 20px;
            border-bottom: 1px solid #e9ecef;
            font-weight: 600;
            font-size: 16px;
        }}
        .details-content {{
            padding: 20px;
        }}
        .details-list {{
            list-style: none;
            padding: 0;
            margin: 0;
        }}
        .details-list li {{
            padding: 8px 0;
            border-bottom: 1px solid #f1f3f4;
            display: flex;
            justify-content: space-between;
        }}
        .details-list li:last-child {{
            border-bottom: none;
        }}
        .label {{
            font-weight: 600;
            color: #495057;
        }}
        .value {{
            color: #6c757d;
            text-align: right;
        }}
        .suggested-action {{ 
            background-color: #e7f3ff; 
            border: 1px solid #bee5eb;
            border-left: 4px solid #17a2b8;
            padding: 20px; 
            margin: 20px 0;
            border-radius: 0 4px 4px 0;
        }}
        .suggested-action h4 {{
            margin: 0 0 10px 0;
            color: #0c5460;
            font-size: 16px;
        }}
        .suggested-action p {{
            margin: 0;
            color: #0c5460;
        }}
        .progress-bar {{
            background-color: #e9ecef;
            border-radius: 4px;
            overflow: hidden;
            height: 8px;
            margin: 10px 0;
        }}
        .progress-fill {{
            height: 100%;
            background-color: {progress_color};
            width: {progress_width}%;
            transition: width 0.3s ease;
        }}
        .footer {{ 
            background-color: #343a40; 
            color: #adb5bd; 
            padding: 20px; 
            text-align: center; 
            font-size: 14px;
        }}
        .footer a {{
            color: #6c757d;
            text-decoration: none;
        }}
        .code-block {{
            background-color: #f8f9fa;
            border: 1px solid #e9ecef;
            border-radius: 4px;
            padding: 15px;
            font-family: monospace;
            font-size: 13px;
            color: #495057;
            overflow-x: auto;
            margin: 15px 0;
        }}
        .button {{
            display: inline-block;
            background-color: {header_color};
            color: white;
            padding: 12px 24px;
            text-decoration: none;
            border-radius: 4px;
            font-weight: 600;
            margin: 15px 0;
        }}
        .timestamp {{
            color: #6c757d;
            font-size: 14px;
            margin-top: 20px;
            padding-top: 20px;
            border-top: 1px solid #e9ecef;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{emoji} {title}</h1>
            <p>{subtitle}</p>
        </div>
        
        <div class="content">
            <div class="alert-level">{level}</div>
            
            <div class="message-box">
                {main_message}
            </div>
            
            {details_section}
            
            {progress_section}
            
            {suggested_action_section}
            
            {additional_content}
            
            <div class="timestamp">
                📅 {timestamp}
            </div>
        </div>
        
        <div class="footer">
            <p>{footer_text}</p>
            {footer_links}
        </div>
    </div>
</body>
</html>"""

    @staticmethod
    def get_level_config(level: NotificationLevel) -> Dict[str, str]:
        """Retorna configurações de cor baseadas no nível"""
        configs = {
            NotificationLevel.CRITICAL: {
                "header_color": "#dc3545",
                "level_bg_color": "#f8d7da", 
                "level_text_color": "#721c24",
                "progress_color": "#dc3545",
                "emoji": "🚨"
            },
            NotificationLevel.ERROR: {
                "header_color": "#fd7e14",
                "level_bg_color": "#ffeaa7",
                "level_text_color": "#856404", 
                "progress_color": "#fd7e14",
                "emoji": "❌"
            },
            NotificationLevel.WARNING: {
                "header_color": "#ffc107",
                "level_bg_color": "#fff3cd",
                "level_text_color": "#856404",
                "progress_color": "#ffc107", 
                "emoji": "⚠️"
            },
            NotificationLevel.INFO: {
                "header_color": "#17a2b8",
                "level_bg_color": "#d1ecf1",
                "level_text_color": "#0c5460",
                "progress_color": "#17a2b8",
                "emoji": "ℹ️"
            }
        }
        return configs.get(level, configs[NotificationLevel.INFO])

    @classmethod
    def build_details_section(cls, details: Dict[str, Any]) -> str:
        """Constrói seção de detalhes"""
        if not details:
            return ""
            
        details_items = []
        for key, value in details.items():
            if isinstance(value, (int, float)) and "token" in key.lower():
                value = f"{value:,}"  # Formatar números com separador
            details_items.append(f"""
                <li>
                    <span class="label">{key}:</span>
                    <span class="value">{value}</span>
                </li>
            """)
        
        return f"""
        <div class="details">
            <div class="details-header">📋 Detalhes</div>
            <div class="details-content">
                <ul class="details-list">
                    {''.join(details_items)}
                </ul>
            </div>
        </div>
        """

    @classmethod
    def build_progress_section(cls, current: int, maximum: int, label: str = "Uso") -> str:
        """Constrói seção de progresso"""
        if not current or not maximum:
            return ""
            
        percentage = min((current / maximum) * 100, 100)
        return f"""
        <div class="details">
            <div class="details-header">📊 {label}</div>
            <div class="details-content">
                <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                    <span>{current:,} / {maximum:,}</span>
                    <span>{percentage:.1f}%</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: {percentage}%;"></div>
                </div>
            </div>
        </div>
        """

    @classmethod
    def build_suggested_action_section(cls, action: str) -> str:
        """Constrói seção de ação sugerida"""
        if not action:
            return ""
            
        return f"""
        <div class="suggested-action">
            <h4>💡 Ação Sugerida</h4>
            <p>{action}</p>
        </div>
        """

class NotificationService:
    """Serviço para envio de notificações por diferentes canais."""
    
    def __init__(self, db_session=None):
        self.db = db_session
        self.template_builder = EmailTemplateBuilder()
    
    def _get_emoji_for_subject(self, level: NotificationLevel) -> str:
        """Retorna emoji para o assunto do email"""
        config = self.template_builder.get_level_config(level)
        return config["emoji"]
    
    async def send_whatsapp_alert(
        self,
        alert_type: str,
        tenant_id: int,
        tenant_name: str,
        device_id: int,
        device_name: str,
        level: str,
        message: str,
        channel: str = "email",
        target: str = None,
        custom_subject: str = None,
        custom_message: str = None,
        error_code: str = None,
        suggested_action: str = None,
        details: Dict[str, Any] = None
    ) -> bool:
        """
        Envia alertas específicos do WhatsApp com template HTML
        """
        try:
            # Converter level para enum
            notification_level = NotificationLevel(level.lower())
            
            # Subject
            emoji = self._get_emoji_for_subject(notification_level)
            subject = custom_subject or f"{emoji} [WhatsApp Service] {level.upper()} - {device_name}"
            
            # Preparar detalhes
            alert_details = {
                "Tenant": f"{tenant_name} (ID: {tenant_id})",
                "Dispositivo": f"{device_name} (ID: {device_id})",
                "Tipo de Alerta": alert_type,
                "Nível": level.upper()
            }
            
            if error_code:
                alert_details["Código do Erro"] = error_code
                
            if details:
                alert_details.update(details)
            
            # Construir HTML
            body = self._build_whatsapp_alert_email(
                level=notification_level,
                title=f"Alerta WhatsApp - {device_name}",
                tenant_name=tenant_name,
                message=custom_message or message,
                details=alert_details,
                suggested_action=suggested_action
            )
            
            if channel == "email" and target:
                return await self._send_email(target, subject, body)
            elif channel == "webhook" and target:
                webhook_payload = {
                    "type": "whatsapp_alert",
                    "alert_type": alert_type,
                    "tenant_id": tenant_id,
                    "tenant_name": tenant_name,
                    "device_id": device_id,
                    "device_name": device_name,
                    "level": level,
                    "message": message,
                    "error_code": error_code,
                    "suggested_action": suggested_action,
                    "details": details,
                    "timestamp": datetime.now().isoformat()
                }
                return await self._send_webhook(target, webhook_payload)
            
            return False
            
        except Exception as e:
            logger.error(f"Error sending WhatsApp alert: {e}")
            return False
    
    def _build_whatsapp_alert_email(
        self,
        level: NotificationLevel,
        title: str,
        tenant_name: str,
        message: str,
        details: Dict[str, Any],
        suggested_action: str = None
    ) -> str:
        """Constrói email HTML para alerta do WhatsApp"""
        
        try:
            config = self.template_builder.get_level_config(level)
            
            # Limpar e validar dados
            safe_message = str(message).replace('\n', '<br>').replace('\r', '')
            safe_suggested_action = str(suggested_action).replace('\n', '<br>').replace('\r', '') if suggested_action else ""
            
            # Construir seções
            details_section = self.template_builder.build_details_section(details) if details else ""
            suggested_action_section = self.template_builder.build_suggested_action_section(safe_suggested_action) if safe_suggested_action else ""
            
            # Construir template
            html_content = self.template_builder.BASE_TEMPLATE.format(
                header_color=config["header_color"],
                level_bg_color=config["level_bg_color"],
                level_text_color=config["level_text_color"],
                progress_color=config["progress_color"],
                progress_width=0,  # Sem barra de progresso para alertas WhatsApp
                emoji=config["emoji"],
                title=title,
                subtitle=f"Alerta do Sistema WhatsApp Service - {tenant_name}",
                level=level.value.upper(),
                main_message=f"<p>{safe_message}</p>",
                details_section=details_section,
                progress_section="",  # Sem barra de progresso
                suggested_action_section=suggested_action_section,
                additional_content="",
                timestamp=datetime.now().strftime('%d/%m/%Y às %H:%M:%S'),
                footer_text="WhatsApp Service - Sistema de Monitoramento Automático",
                footer_links=""
            )
            
            return html_content
            
        except Exception as e:
            logger.error(f"Error building WhatsApp alert email: {e}")
            # Fallback para email simples em caso de erro no template
            return f"""
            <html>
            <body>
                <h2>{title}</h2>
                <p>{message}</p>
                <p><strong>Tenant:</strong> {tenant_name}</p>
                <p><strong>Timestamp:</strong> {datetime.now().strftime('%d/%m/%Y às %H:%M:%S')}</p>
                {f'<p><strong>Ação Sugerida:</strong> {suggested_action}</p>' if suggested_action else ''}
            </body>
            </html>
            """
    
    async def _send_email(self, to_email: str, subject: str, body: str) -> bool:
        """Envia notificação por email."""
        try:
            # Configuração de email
            from_email = settings.EMAIL_FROM or "thiagoparaizo+ASSISTENTE-VIRTUAL@gmail.com"
            smtp_server = settings.SMTP_SERVER or "smtp.gmail.com"
            smtp_port = settings.SMTP_PORT or 587
            smtp_user = settings.SMTP_USER
            smtp_password = settings.SMTP_PASSWORD
            
            if not smtp_user or not smtp_password:
                logger.error("SMTP credentials not configured")
                return False
            
            # Criar mensagem
            message = MIMEMultipart("alternative")
            message["From"] = from_email
            message["To"] = to_email
            message["Subject"] = subject
            
            # Adicionar corpo HTML
            html_part = MIMEText(body, "html", "utf-8")
            message.attach(html_part)
            
            # Enviar email
            async with aiosmtplib.SMTP(hostname=smtp_server, port=smtp_port, start_tls=settings.SMTP_TLS) as smtp:
                await smtp.login(smtp_user, smtp_password)
                await smtp.send_message(message)
            
            logger.info(f"Email sent successfully to {to_email}")
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
                logger.info(f"Webhook sent successfully to {webhook_url}")
                return True
                
        except Exception as e:
            logger.error(f"Error sending webhook notification: {e}")
            return False