import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from dotenv import load_dotenv

from app.services.token_counter import TokenCounterService
load_dotenv()

from app.api.router import api_router
from app.core.config import settings

from app.core.redis import init_redis_pool, close_redis_connections

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    version="0.1.0",
)

os.makedirs(settings.VECTOR_DB_PATH, exist_ok=True)
os.makedirs(settings.MEMORY_DB_PATH, exist_ok=True)

@app.on_event("startup")
async def startup_db_client():
    await init_redis_pool()
    # Criar uma sessão global para serviços
    from sqlalchemy.orm import sessionmaker
    from app.db.session import engine
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Criar instância global do TokenCounterService 
    # (opcional, mas pode ser útil para processos assíncronos)
    app.state.token_counter = TokenCounterService(SessionLocal())
    
    import logging
    logger = logging.getLogger("main")
    logger.info(f"🚀 {settings.PROJECT_NAME} iniciado com sucesso!")
    logger.info(f"📊 Health check disponível em: /api/v1/health/detailed")
    logger.info(f"🔍 Health check básico em: /api/v1/health")
    logger.info(f"💾 Health check database em: /api/v1/health/database")

@app.on_event("shutdown")
async def shutdown_db_client():
    await close_redis_connections()
    
    import logging
    logger = logging.getLogger("main")
    logger.info("🛑 Aplicação finalizada")

# iniciar as variaveis de ambiente dotenv


# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Incluir rotas da API
app.include_router(api_router, prefix=settings.API_V1_STR)

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True if settings.DEBUG else False,
    )