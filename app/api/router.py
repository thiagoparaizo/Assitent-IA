import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
import time
import os
import psutil
import asyncio

from app.api.deps import get_db
from app.core.config import settings

from app.api.endpoints import auth, users, dashboard, llm_admin, whatsapp, tenants, conversations, appointments, webhook, knowledge, agents, internal, token_limits, whatsapp_notifications, whatsapp_monitoring


api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(whatsapp.router, prefix="/whatsapp", tags=["whatsapp"])
api_router.include_router(tenants.router, prefix="/tenants", tags=["tenants"])
api_router.include_router(conversations.router, prefix="/conversations", tags=["conversas"])
#api_router.include_router(appointments.router, prefix="/appointments", tags=["agendamentos"])
api_router.include_router(webhook.router, prefix="/webhook", tags=["webhook"])
api_router.include_router(knowledge.router, prefix="/knowledge", tags=["conhecimento"])
api_router.include_router(agents.router, prefix="/agents", tags=["agentes"])
api_router.include_router(internal.router, prefix="/internal", tags=["internal"])
api_router.include_router(llm_admin.router, prefix="/llm", tags=["llm"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(token_limits.router, prefix="/token-limits", tags=["token-limits"])
api_router.include_router(users.router, prefix="/user", tags=["user"])
api_router.include_router(whatsapp_notifications.router, prefix="/whatsapp-notifications", tags=["whatsapp-notifications"])
api_router.include_router(whatsapp_monitoring.router, prefix="/whatsapp-monitoring", tags=["whatsapp-monitoring"])


@api_router.get("/health", tags=["health"])
def basic_health_check():
    """Endpoint básico de health check (compatibilidade)"""
    return {"status": "healthy", "version": "0.1.0"}

@api_router.get("/health/detailed", tags=["health"])
def detailed_health_check(db: Session = Depends(get_db)):
    """
    Endpoint detalhado de health check com testes de conectividade
    Ideal para configuração no Coolify e monitoramento
    """
    start_time = time.time()
    health_status = {
        "status": "healthy",
        "version": "0.1.0",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {}
    }
    
    overall_healthy = True
    failed_checks = []
    
    # 1. Teste de conectividade com o banco de dados
    try:
        db_start = time.time()
        # Executa uma query simples para testar a conectividade
        result = db.execute(text("SELECT 1 as test")).fetchone()
        db_duration = (time.time() - db_start) * 1000  # em ms
        
        if result and result[0] == 1:
            health_status["checks"]["database"] = {
                "status": "healthy",
                "response_time_ms": round(db_duration, 2),
                "message": "Database connection successful"
            }
        else:
            health_status["checks"]["database"] = {
                "status": "unhealthy",
                "response_time_ms": round(db_duration, 2),
                "message": "Database query returned unexpected result"
            }
            overall_healthy = False
            failed_checks.append("Database query failed")
            
    except Exception as e:
        health_status["checks"]["database"] = {
            "status": "unhealthy",
            "response_time_ms": None,
            "message": f"Database connection failed: {str(e)}"
        }
        overall_healthy = False
        failed_checks.append("Database connection failed - Exception: " + str(e))
    
    # 2. Verificação de memória do sistema
    try:
        memory = psutil.virtual_memory()
        memory_usage_percent = memory.percent
        
        if memory_usage_percent < 90:
            memory_status = "healthy"
            memory_message = f"Memory usage: {memory_usage_percent}%"
        else:
            memory_status = "warning"
            memory_message = f"High memory usage: {memory_usage_percent}%"
            
        health_status["checks"]["memory"] = {
            "status": memory_status,
            "usage_percent": memory_usage_percent,
            "available_gb": round(memory.available / (1024**3), 2),
            "message": memory_message
        }
        
    except Exception as e:
        health_status["checks"]["memory"] = {
            "status": "error",
            "message": f"Memory check failed: {str(e)}"
        }
        failed_checks.append("Memory check failed - Exception: " + str(e))
    
    # 3. Verificação de disco
    try:
        disk = psutil.disk_usage('/')
        disk_usage_percent = (disk.used / disk.total) * 100
        
        if disk_usage_percent < 85:
            disk_status = "healthy"
            disk_message = f"Disk usage: {disk_usage_percent:.1f}%"
        elif disk_usage_percent < 95:
            disk_status = "warning"
            disk_message = f"High disk usage: {disk_usage_percent:.1f}%"
        else:
            disk_status = "critical"
            disk_message = f"Critical disk usage: {disk_usage_percent:.1f}%"
            overall_healthy = False
            failed_checks.append("Critical disk usage")
            
        health_status["checks"]["disk"] = {
            "status": disk_status,
            "usage_percent": round(disk_usage_percent, 1),
            "free_gb": round(disk.free / (1024**3), 2),
            "message": disk_message
        }
        
    except Exception as e:
        health_status["checks"]["disk"] = {
            "status": "error",
            "message": f"Disk check failed: {str(e)}"
        }
        failed_checks.append("Disk check failed - Exception: " + str(e))
    
    # 4. Verificação de diretórios necessários
    try:
        required_dirs = [
            settings.VECTOR_DB_PATH,
            settings.MEMORY_DB_PATH,
            "./storage/temp"
        ]
        
        missing_dirs = []
        for dir_path in required_dirs:
            if not os.path.exists(dir_path):
                missing_dirs.append(dir_path)
        
        if not missing_dirs:
            health_status["checks"]["storage"] = {
                "status": "healthy",
                "message": "All required directories exist"
            }
        else:
            health_status["checks"]["storage"] = {
                "status": "warning",
                "message": f"Missing directories: {', '.join(missing_dirs)}"
            }
            failed_checks.append("Missing directories")
            
    except Exception as e:
        health_status["checks"]["storage"] = {
            "status": "error",
            "message": f"Storage check failed: {str(e)}"
        }
        failed_checks.append("Storage check failed - Exception: " + str(e))
    
    # 5. Verificação de variáveis de ambiente críticas
    try:
        critical_env_vars = [
            "POSTGRES_SERVER",
            "POSTGRES_USER",
            "POSTGRES_DB",
            "SECRET_KEY"
        ]
        
        missing_vars = []
        for var in critical_env_vars:
            if not getattr(settings, var, None):
                missing_vars.append(var)
        
        if not missing_vars:
            health_status["checks"]["environment"] = {
                "status": "healthy",
                "message": "All critical environment variables are set"
            }
        else:
            health_status["checks"]["environment"] = {
                "status": "unhealthy",
                "message": f"Missing critical environment variables: {', '.join(missing_vars)}"
            }
            overall_healthy = False
            failed_checks.append("Missing critical environment variables")
            
    except Exception as e:
        health_status["checks"]["environment"] = {
            "status": "error",
            "message": f"Environment check failed: {str(e)}"
        }
        failed_checks.append("Environment check failed - Exception: " + str(e))
    
    # 6. Tempo total de resposta
    total_duration = (time.time() - start_time) * 1000
    health_status["response_time_ms"] = round(total_duration, 2)
    
    # Status geral
    if overall_healthy:
        health_status["status"] = "healthy"
    else:
        health_status["status"] = "unhealthy"
    
    # Se unhealthy, retorna status HTTP 503
    if not overall_healthy:
        # notificação por email
        from app.services.notification import NotificationService
        
        try:
            
            NotificationService().send_health_check_alert(
                service_name="AI Assistant API",
                status="unhealthy", 
                failed_checks=failed_checks,
                details=health_status["checks"],
                target="thiagoparaizo+API-Health@gmail.com"
            )
            
            # message=f"""🚨🚨 AÇÃO URGENTE NECESSÁRIA 🚨🚨 - API Healt Check Error
            # Verificar a saúda da aplicação devido a alertas do health check.
            
            
            # Detalhes:
            # {json.dumps(health_status, indent=4)}
            
            # """
            
            # NotificationService()._send_email('thiagoparaizo+API-Health@gmail.com', 'ASSISTENTE IA - AVISO: ERRO NO HEALTH CHECK', message)
            
        except Exception as e:
            print(f"ROUTER[detailed_health_check]: Error sending email notification: {e}")
            
            
        raise HTTPException(status_code=503, detail=health_status)
    
    return health_status

@api_router.get("/health/database", tags=["health"])
def database_health_check(db: Session = Depends(get_db)):
    """
    Endpoint específico para health check do banco de dados
    """
    try:
        start_time = time.time()
        
        # Teste básico de conectividade
        db.execute(text("SELECT 1")).fetchone()
        
        # Teste de contagem de tabelas (verifica se o schema existe)
        tables_count = db.execute(text("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)).fetchone()[0]
        
        # Teste de escrita (transaction)
        try:
            db.execute(text("CREATE TEMP TABLE health_test (id int)"))
            db.execute(text("INSERT INTO health_test VALUES (1)"))
            db.execute(text("DROP TABLE health_test"))
            db.commit()
            write_test = True
        except:
            write_test = False
            db.rollback()
        
        duration = (time.time() - start_time) * 1000
        
        return {
            "status": "healthy",
            "database": {
                "connected": True,
                "tables_count": tables_count,
                "write_test": write_test,
                "response_time_ms": round(duration, 2)
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=503, 
            detail={
                "status": "unhealthy",
                "database": {
                    "connected": False,
                    "error": str(e)
                },
                "timestamp": datetime.utcnow().isoformat()
            }
        )

@api_router.get("/health/redis", tags=["health"])
async def redis_health_check():
    """
    Endpoint específico para health check do Redis
    """
    try:
        from app.core.redis import get_redis
        
        start_time = time.time()
        redis_client = await get_redis()
        
        # Teste de ping
        pong = await redis_client.ping()
        
        # Teste de escrita/leitura
        test_key = "health_check_test"
        await redis_client.set(test_key, "test_value", ex=60)
        test_value = await redis_client.get(test_key)
        await redis_client.delete(test_key)
        
        duration = (time.time() - start_time) * 1000
        
        return {
            "status": "healthy",
            "redis": {
                "connected": True,
                "ping": pong,
                "read_write_test": test_value.decode() == "test_value" if test_value else False,
                "response_time_ms": round(duration, 2)
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "redis": {
                    "connected": False,
                    "error": str(e)
                },
                "timestamp": datetime.utcnow().isoformat()
            }
        )