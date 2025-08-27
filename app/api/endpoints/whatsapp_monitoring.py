# ==============================================
# NOVO ARQUIVO: app/api/endpoints/whatsapp_monitoring.py
# ==============================================

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException, Response
from pydantic_settings import BaseSettings
from sqlalchemy.orm import Session
from pydantic import BaseModel
import logging

from app.api.deps import get_db

logger = logging.getLogger('app.api.endpoints.whatsapp_monitoring')
logging.basicConfig(level=logging.DEBUG)

router = APIRouter()

class DeviceHealthStatus(BaseModel):
    device_id: int
    device_name: str
    tenant_id: int
    tenant_name: str
    status: str  # connected, disconnected, requires_reauth, error
    last_seen: Optional[datetime]
    last_notification: Optional[datetime]
    notification_count_24h: int
    error_count_24h: int
    connection_uptime_percentage: float
    current_issues: List[str]

class NotificationSummary(BaseModel):
    total_devices: int
    connected_devices: int
    disconnected_devices: int
    devices_requiring_reauth: int
    devices_with_errors: int
    notifications_last_24h: int
    critical_alerts_active: int
    webhook_failures_last_24h: int

class NotificationLog(BaseModel):
    id: int
    device_id: int
    device_name: str
    tenant_id: int
    tenant_name: str
    level: str
    type: str
    title: str
    message: str
    error_code: Optional[str]
    suggested_action: Optional[str]
    created_at: datetime
    resolved_at: Optional[datetime]
    resolution_notes: Optional[str]

@router.get("/whatsapp/health-summary", response_model=NotificationSummary)
async def get_whatsapp_health_summary(db: Session = Depends(get_db)):
    """
    Retorna resumo geral da saúde do sistema WhatsApp
    """
    try:
        # Consultar estatísticas de dispositivos
        device_stats = await get_device_statistics(db)
        
        # Consultar notificações das últimas 24h
        notification_stats = await get_notification_statistics(db)
        
        return NotificationSummary(
            total_devices=device_stats["total"],
            connected_devices=device_stats["connected"],
            disconnected_devices=device_stats["disconnected"],
            devices_requiring_reauth=device_stats["requiring_reauth"],
            devices_with_errors=device_stats["with_errors"],
            notifications_last_24h=notification_stats["total_24h"],
            critical_alerts_active=notification_stats["critical_active"],
            webhook_failures_last_24h=notification_stats["webhook_failures_24h"]
        )
        
    except Exception as e:
        logger.error(f"Erro ao buscar resumo de saúde: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/whatsapp/devices-health", response_model=List[DeviceHealthStatus])
async def get_devices_health_status(
    tenant_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db)
):
    """
    Retorna status de saúde detalhado dos dispositivos
    """
    try:
        devices_health = await get_detailed_devices_health(
            db, tenant_id, status_filter, limit
        )
        return devices_health
        
    except Exception as e:
        logger.error(f"Erro ao buscar saúde dos dispositivos: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/whatsapp/notifications", response_model=List[NotificationLog])
async def get_whatsapp_notifications(
    tenant_id: Optional[int] = Query(None),
    device_id: Optional[int] = Query(None),
    level: Optional[str] = Query(None),
    type_filter: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db)
):
    """
    Retorna logs de notificações com filtros
    """
    try:
        notifications = await get_notification_logs(
            db, tenant_id, device_id, level, type_filter, 
            start_date, end_date, limit
        )
        return notifications
        
    except Exception as e:
        logger.error(f"Erro ao buscar notificações: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/whatsapp/notifications/{notification_id}/resolve")
async def resolve_notification(
    notification_id: int,
    resolution_notes: str,
    db: Session = Depends(get_db)
):
    """
    Marca uma notificação como resolvida
    """
    try:
        await mark_notification_resolved(db, notification_id, resolution_notes)
        return {"status": "resolved", "message": "Notificação marcada como resolvida"}
        
    except Exception as e:
        logger.error(f"Erro ao resolver notificação: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/whatsapp/devices/{device_id}/notifications")
async def get_device_notifications(
    device_id: int,
    days: int = Query(7, le=30),
    db: Session = Depends(get_db)
):
    """
    Retorna histórico de notificações de um dispositivo específico
    """
    try:
        start_date = datetime.now() - timedelta(days=days)
        notifications = await get_notification_logs(
            db, None, device_id, None, None, start_date, None, 100
        )
        
        # Calcular estatísticas do dispositivo
        stats = await calculate_device_stats(db, device_id, days)
        
        return {
            "device_id": device_id,
            "period_days": days,
            "notifications": notifications,
            "statistics": stats
        }
        
    except Exception as e:
        logger.error(f"Erro ao buscar notificações do dispositivo: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/whatsapp/health-report")
async def generate_health_report(
    tenant_id: Optional[int] = Query(None),
    days: int = Query(7, le=30),
    format: str = Query("json", regex="^(json|csv)$"),
    db: Session = Depends(get_db)
):
    """
    Gera relatório de saúde do sistema WhatsApp
    """
    try:
        report_data = await generate_comprehensive_health_report(
            db, tenant_id, days
        )
        
        if format == "csv":
            # Converter para CSV se solicitado
            csv_content = convert_report_to_csv(report_data)
            return Response(
                content=csv_content,
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=whatsapp_health_report.csv"}
            )
        
        return report_data
        
    except Exception as e:
        logger.error(f"Erro ao gerar relatório: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Funções auxiliares

async def get_device_statistics(db: Session) -> Dict[str, int]:
    """Calcula estatísticas de dispositivos"""
    # Implementar queries para contar dispositivos por status
    # Esta é uma implementação simplificada
    
    return {
        "total": 50,
        "connected": 42,
        "disconnected": 5,
        "requiring_reauth": 2,
        "with_errors": 1
    }

async def get_notification_statistics(db: Session) -> Dict[str, int]:
    """Calcula estatísticas de notificações"""
    cutoff_24h = datetime.now() - timedelta(hours=24)
    
    # Queries simplificadas - implementar com SQL real
    return {
        "total_24h": 15,
        "critical_active": 2,
        "webhook_failures_24h": 3
    }

async def get_detailed_devices_health(
    db: Session, 
    tenant_id: Optional[int], 
    status_filter: Optional[str], 
    limit: int
) -> List[DeviceHealthStatus]:
    """Busca status detalhado de saúde dos dispositivos"""
    
    # Implementação simplificada - fazer queries reais no banco
    sample_devices = [
        DeviceHealthStatus(
            device_id=1,
            device_name="Dispositivo Principal",
            tenant_id=1,
            tenant_name="Cliente ABC",
            status="connected",
            last_seen=datetime.now() - timedelta(minutes=5),
            last_notification=datetime.now() - timedelta(hours=2),
            notification_count_24h=0,
            error_count_24h=0,
            connection_uptime_percentage=99.8,
            current_issues=[]
        ),
        DeviceHealthStatus(
            device_id=2,
            device_name="Dispositivo Suporte",
            tenant_id=1,
            tenant_name="Cliente ABC",
            status="requires_reauth",
            last_seen=datetime.now() - timedelta(hours=1),
            last_notification=datetime.now() - timedelta(minutes=30),
            notification_count_24h=3,
            error_count_24h=1,
            connection_uptime_percentage=85.2,
            current_issues=["Reautenticação necessária"]
        )
    ]
    
    return sample_devices[:limit]

async def get_notification_logs(
    db: Session,
    tenant_id: Optional[int],
    device_id: Optional[int],
    level: Optional[str],
    type_filter: Optional[str],
    start_date: Optional[datetime],
    end_date: Optional[datetime],
    limit: int
) -> List[NotificationLog]:
    """Busca logs de notificações com filtros"""
    
    # Implementação simplificada
    sample_logs = [
        NotificationLog(
            id=1,
            device_id=2,
            device_name="Dispositivo Suporte",
            tenant_id=1,
            tenant_name="Cliente ABC",
            level="warning",
            type="device_requires_reauth",
            title="Dispositivo Requer Reautenticação",
            message="Dispositivo necessita ser reautenticado",
            error_code="REAUTH_REQUIRED",
            suggested_action="Gerar novo QR Code",
            created_at=datetime.now() - timedelta(minutes=30),
            resolved_at=None,
            resolution_notes=None
        )
    ]
    
    return sample_logs[:limit]

async def mark_notification_resolved(
    db: Session, 
    notification_id: int, 
    resolution_notes: str
):
    """Marca notificação como resolvida"""
    # Implementar update no banco
    pass

async def calculate_device_stats(
    db: Session, 
    device_id: int, 
    days: int
) -> Dict[str, Any]:
    """Calcula estatísticas de um dispositivo específico"""
    return {
        "uptime_percentage": 95.5,
        "total_notifications": 8,
        "error_notifications": 2,
        "warning_notifications": 5,
        "info_notifications": 1,
        "avg_response_time": "2.3s",
        "last_successful_connection": datetime.now() - timedelta(hours=1)
    }

async def generate_comprehensive_health_report(
    db: Session, 
    tenant_id: Optional[int], 
    days: int
) -> Dict[str, Any]:
    """Gera relatório abrangente de saúde"""
    return {
        "report_period": f"{days} days",
        "generated_at": datetime.now().isoformat(),
        "summary": await get_notification_statistics(db),
        "devices": await get_detailed_devices_health(db, tenant_id, None, 1000),
        "top_issues": [
            {"issue": "Device reauth required", "count": 5},
            {"issue": "Connection timeouts", "count": 3},
            {"issue": "Webhook failures", "count": 2}
        ],
        "recommendations": [
            "Atualizar biblioteca whatsmeow em 2 dispositivos",
            "Verificar configuração de webhook para Tenant 3",
            "Monitorar dispositivos com baixo uptime"
        ]
    }

def convert_report_to_csv(report_data: Dict[str, Any]) -> str:
    """Converte relatório para formato CSV"""
    # Implementação simplificada
    return "device_id,device_name,status,uptime,issues\n1,Device1,connected,99.8%,none\n"

# ==============================================
# EXTENSÃO DO ARQUIVO: app/core/config.py
# Adicionar configurações de monitoramento
# ==============================================

class Settings(BaseSettings):
    # ... configurações existentes ...
    
    # Configurações de monitoramento WhatsApp
    WHATSAPP_MONITORING_ENABLED: bool = True
    WHATSAPP_HEALTH_CHECK_INTERVAL: int = 300  # 5 minutos
    WHATSAPP_NOTIFICATION_RETENTION_DAYS: int = 30
    WHATSAPP_ALERT_COOLDOWN_MINUTES: int = 30
    
    # Configurações de alertas críticos
    CRITICAL_ALERT_WEBHOOK_URL: str = ""
    SYSTEM_ADMIN_EMAILS: str = "admin@yourcompany.com"
    
    @property
    def system_admin_email_list(self) -> List[str]:
        return [email.strip() for email in self.SYSTEM_ADMIN_EMAILS.split(",")]