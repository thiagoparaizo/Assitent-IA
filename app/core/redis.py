import os
import asyncio
from typing import Optional
import redis.asyncio as redis
from app.core.config import settings

# Singleton para o pool de conexões Redis
_redis_pool: Optional[redis.ConnectionPool] = None
_redis_client: Optional[redis.Redis] = None

# Lock para sincronização
_lock = asyncio.Lock()

async def init_redis_pool(force: bool = False) -> redis.ConnectionPool:
    """
    Inicializa o pool de conexões Redis.
    Args:
        force: Se True, recria o pool mesmo se já existir
    Returns:
        ConnectionPool do Redis
    """
    global _redis_pool
    
    async with _lock:
        if _redis_pool is None or force:
            # Parse a URL do Redis para extrair componentes
            url = settings.REDIS_URL
            
            # Configurações de connection pool
            pool_size = int(os.getenv("REDIS_POOL_SIZE", "10"))
            pool_timeout = float(os.getenv("REDIS_POOL_TIMEOUT", "30"))
            
            try:
                _redis_pool = redis.ConnectionPool.from_url(
                    url,
                    max_connections=pool_size,
                    socket_timeout=pool_timeout,
                    socket_connect_timeout=5.0,
                    retry_on_timeout=True,
                    health_check_interval=30
                )
                print(f"Initialized Redis connection pool with size {pool_size}")
            except Exception as e:
                print(f"Error initializing Redis connection pool: {e}")
                raise
    
    return _redis_pool

async def get_redis() -> redis.Redis:
    """
    Obtém uma conexão Redis do pool.
    
    Returns:
        Cliente Redis
    """
    global _redis_client, _redis_pool
    
    if _redis_pool is None:
        await init_redis_pool()
    
    if _redis_client is None:
        _redis_client = redis.Redis(connection_pool=_redis_pool)
    
    return _redis_client

async def close_redis_connections():
    """Fecha todas as conexões Redis ao encerrar a aplicação."""
    global _redis_client, _redis_pool
    
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None
    
    if _redis_pool is not None:
        await _redis_pool.disconnect()
        _redis_pool = None