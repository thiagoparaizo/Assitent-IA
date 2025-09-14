# app/utils/health_check.py
"""
Utilitários para health check da aplicação
"""

import asyncio
import time
from datetime import datetime
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import text
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

class HealthChecker:
    """Classe para centralizar verificações de saúde"""
    
    @staticmethod
    def check_database_connection(db: Session) -> Dict[str, Any]:
        """Verifica conectividade e performance do banco"""
        try:
            start_time = time.time()
            
            # Teste básico de conectividade
            result = db.execute(text("SELECT 1 as test")).fetchone()
            basic_test = result and result[0] == 1
            
            # Teste de performance com query mais complexa
            db.execute(text("""
                SELECT 
                    COUNT(*) as total_tables,
                    CURRENT_TIMESTAMP as db_time
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """)).fetchone()
            
            duration = (time.time() - start_time) * 1000
            
            return {
                "status": "healthy" if basic_test else "unhealthy",
                "connected": basic_test,
                "response_time_ms": round(duration, 2),
                "details": {
                    "basic_test": basic_test,
                    "performance_test": duration < 1000,  # < 1 segundo
                }
            }
            
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                "status": "unhealthy",
                "connected": False,
                "error": str(e),
                "response_time_ms": None
            }
    
    @staticmethod
    async def check_redis_connection() -> Dict[str, Any]:
        """Verifica conectividade com Redis"""
        try:
            from app.core.redis import get_redis
            
            start_time = time.time()
            redis_client = await get_redis()
            
            # Teste de ping
            pong = await redis_client.ping()
            
            # Teste de operações básicas
            test_key = f"health_check:{datetime.utcnow().timestamp()}"
            await redis_client.set(test_key, "test", ex=30)
            value = await redis_client.get(test_key)
            await redis_client.delete(test_key)
            
            duration = (time.time() - start_time) * 1000
            
            return {
                "status": "healthy",
                "connected": True,
                "ping": pong,
                "operations_test": value.decode() == "test" if value else False,
                "response_time_ms": round(duration, 2)
            }
            
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return {
                "status": "unhealthy",
                "connected": False,
                "error": str(e),
                "response_time_ms": None
            }
    
    @staticmethod
    def check_system_resources() -> Dict[str, Any]:
        """Verifica recursos do sistema"""
        try:
            import psutil
            
            # Memória
            memory = psutil.virtual_memory()
            memory_status = "healthy" if memory.percent < 85 else "warning" if memory.percent < 95 else "critical"
            
            # CPU
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_status = "healthy" if cpu_percent < 80 else "warning" if cpu_percent < 95 else "critical"
            
            # Disco
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            disk_status = "healthy" if disk_percent < 80 else "warning" if disk_percent < 90 else "critical"
            
            return {
                "status": "healthy" if all(s in ["healthy", "warning"] for s in [memory_status, cpu_status, disk_status]) else "unhealthy",
                "memory": {
                    "status": memory_status,
                    "usage_percent": round(memory.percent, 1),
                    "available_gb": round(memory.available / (1024**3), 2)
                },
                "cpu": {
                    "status": cpu_status,
                    "usage_percent": round(cpu_percent, 1)
                },
                "disk": {
                    "status": disk_status,
                    "usage_percent": round(disk_percent, 1),
                    "free_gb": round(disk.free / (1024**3), 2)
                }
            }
            
        except Exception as e:
            logger.error(f"System resources check failed: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    @staticmethod
    def check_application_dependencies() -> Dict[str, Any]:
        """Verifica dependências da aplicação"""
        try:
            import os
            
            # Diretórios necessários
            required_dirs = [
                settings.VECTOR_DB_PATH,
                settings.MEMORY_DB_PATH,
                "./storage/temp"
            ]
            
            missing_dirs = []
            for dir_path in required_dirs:
                if not os.path.exists(dir_path):
                    missing_dirs.append(dir_path)
            
            # Variáveis de ambiente críticas
            critical_vars = {
                "POSTGRES_SERVER": settings.POSTGRES_SERVER,
                "POSTGRES_USER": settings.POSTGRES_USER,
                "POSTGRES_DB": settings.POSTGRES_DB,
                "SECRET_KEY": settings.SECRET_KEY,
                "REDIS_URL": settings.REDIS_URL
            }
            
            missing_vars = [var for var, value in critical_vars.items() if not value]
            
            return {
                "status": "healthy" if not missing_dirs and not missing_vars else "unhealthy",
                "directories": {
                    "status": "healthy" if not missing_dirs else "unhealthy",
                    "missing": missing_dirs
                },
                "environment": {
                    "status": "healthy" if not missing_vars else "unhealthy",
                    "missing_variables": missing_vars
                }
            }
            
        except Exception as e:
            logger.error(f"Dependencies check failed: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

# app/middleware/health_monitoring.py
"""
Middleware para monitoramento contínuo de saúde
"""

import time
import logging
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

class HealthMonitoringMiddleware(BaseHTTPMiddleware):
    """Middleware para monitorar saúde da aplicação"""
    
    def __init__(self, app, enable_logging: bool = True):
        super().__init__(app)
        self.enable_logging = enable_logging
        self.request_count = 0
        self.error_count = 0
        self.last_request_time = time.time()
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        self.request_count += 1
        self.last_request_time = time.time()
        
        try:
            response = await call_next(request)
            
            # Log slow requests
            duration = time.time() - start_time
            if duration > 5.0 and self.enable_logging:  # > 5 segundos
                logger.warning(
                    f"Slow request: {request.method} {request.url.path} "
                    f"took {duration:.2f}s"
                )
            
            return response
            
        except Exception as e:
            self.error_count += 1
            logger.error(f"Request failed: {request.method} {request.url.path} - {str(e)}")
            raise
    
    def get_metrics(self) -> dict:
        """Retorna métricas básicas da aplicação"""
        return {
            "total_requests": self.request_count,
            "total_errors": self.error_count,
            "error_rate": self.error_count / max(self.request_count, 1),
            "last_request_time": self.last_request_time,
            "uptime_seconds": time.time() - getattr(self, 'start_time', time.time())
        }

# Configuração para Coolify
"""
CONFIGURAÇÃO NO COOLIFY:

1. Acesse as configurações do seu serviço no Coolify
2. Vá para a seção "Health Check"
3. Configure os seguintes parâmetros:

Health Check URL: /api/v1/health/detailed
Health Check Method: GET
Health Check Port: 8000 (ou a porta que sua aplicação usa)
Health Check Interval: 30s (recomendado)
Health Check Timeout: 10s
Health Check Retries: 3
Health Check Start Period: 60s (tempo para a aplicação inicializar)

4. Para um health check mais simples (apenas banco):
   Alternativamente use: /api/v1/health/database

5. Para monitoramento básico:
   Use: /api/v1/health

CONFIGURAÇÃO AVANÇADA:
- Para aplicações críticas, use /api/v1/health/detailed
- Para aplicações simples, use /api/v1/health
- Configure alertas para quando o health check falhar por mais de 2 minutos consecutivos

EXEMPLO DE RESPOSTA SAUDÁVEL:
{
  "status": "healthy",
  "version": "0.1.0",
  "timestamp": "2025-01-20T15:30:45.123456",
  "checks": {
    "database": {
      "status": "healthy",
      "response_time_ms": 45.67,
      "message": "Database connection successful"
    },
    "memory": {
      "status": "healthy",
      "usage_percent": 65.2,
      "available_gb": 2.1,
      "message": "Memory usage: 65.2%"
    }
  },
  "response_time_ms": 156.78
}

EXEMPLO DE RESPOSTA COM PROBLEMAS (Status HTTP 503):
{
  "status": "unhealthy",
  "version": "0.1.0",
  "timestamp": "2025-01-20T15:30:45.123456",
  "checks": {
    "database": {
      "status": "unhealthy",
      "response_time_ms": null,
      "message": "Database connection failed: connection timeout"
    }
  },
  "response_time_ms": 5000.0
}
"""