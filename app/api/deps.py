import os
from typing import Generator, Optional

from fastapi import Depends, HTTPException, Header, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt
from pydantic import ValidationError
from sqlalchemy.orm import Session

import redis.asyncio as redis

from app.core.config import settings
from app.core.security import ALGORITHM
from app.db.session import SessionLocal
from app.db.models.user import User
from app.schemas.token import TokenPayload
from app.services.agent import AgentService
from app.services.llm import LLMService
from app.services.mcp import MCPService
from app.services.orchestrator import AgentOrchestrator
from app.services.rag import RAGService
from app.services.whatsapp import WhatsAppService

from app.services.config import SystemConfig, load_system_config
from app.services.memory import MemoryService
from app.services.orchestrator import AgentOrchestrator

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")


def get_db() -> Generator:
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()


def get_current_user(
    db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> User:
    print(f"Tentando autenticar com token: {token[:10]}...") # Apenas para debug
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[ALGORITHM]
        )
        token_data = TokenPayload(**payload)
        print(f"Token decodificado com sucesso, sub: {token_data.sub}")
    except (jwt.JWTError, ValidationError) as e:
        print(f"Erro ao decodificar token: {e}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Não foi possível validar as credenciais",
        )
    user = db.query(User).filter(User.id == token_data.sub).first()
    if not user:
        print(f"Usuário não encontrado para ID: {token_data.sub}")
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    print(f"Usuário autenticado: {user.email}")
    return user


def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Usuário inativo")
    return current_user


def get_current_active_superuser(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=400, detail="O usuário não tem privilégios suficientes"
        )
    return current_user


async def get_tenant_id(
    x_tenant_id: Optional[str] = Header(None),
    current_user: Optional[User] = Depends(get_current_user),
) -> str:
    """
    Obtém o ID do tenant a partir do cabeçalho da requisição ou do usuário autenticado.
    """
    # Use header tenant_id if provided
    if x_tenant_id:
        return x_tenant_id
        
    # Use user's tenant_id if available
    if current_user and current_user.tenant_id:
        return str(current_user.tenant_id)
    
    # Default to tenant 1 for development
    return "1"

def get_whatsapp_service() -> WhatsAppService:
    return WhatsAppService()


def get_openai_api_key() -> str:
    return os.getenv("OPENAI_API_KEY")

# Redis client
async def get_redis_client():
    """Obtém cliente Redis."""
    redis_url = settings.REDIS_URL
    return redis.from_url(redis_url)

# Agent Service
async def get_agent_service(
    db: Session = Depends(get_db),
    redis_client = Depends(get_redis_client)
) -> AgentService:
    """
    Obtém o serviço de agentes.
    """
    return AgentService(db, redis_client)

# RAG Service
async def get_rag_service(tenant_id: str = Depends(get_tenant_id)):
    """Obtém o serviço RAG."""
    openai_api_key = os.getenv("OPENAI_API_KEY")
    return RAGService(tenant_id=tenant_id, openai_api_key=openai_api_key)

# LLM Service
async def get_llm_service():
    """Obtém o serviço LLM."""
    openai_api_key = os.getenv("OPENAI_API_KEY")
    return RAGService(api_key=openai_api_key)

# MCP Service
async def get_mcp_service():
    """Obtém o serviço MCP."""
    return MCPService()

# Orchestrator
async def get_orchestrator(
    agent_service: AgentService = Depends(get_agent_service),
    rag_service: RAGService = Depends(get_rag_service),
    redis_client = Depends(get_redis_client),
    openai_api_key: str = Depends(get_openai_api_key)
) -> AgentOrchestrator:
    """
    Obtém o orquestrador de agentes.
    """
    llm_service = LLMService(api_key=openai_api_key)
    return AgentOrchestrator(agent_service, rag_service, redis_client, llm_service)

async def get_enhanced_orchestrator(
    agent_service: AgentService = Depends(get_agent_service),
    rag_service: RAGService = Depends(get_rag_service),
    redis_client = Depends(get_redis_client),
    llm_service: LLMService = Depends(get_llm_service),
    config: SystemConfig = None
) -> AgentOrchestrator:
    """
    Get an enhanced orchestrator with scoring system and memory.
    
    Args:
        agent_service: Agent service
        rag_service: RAG service
        redis_client: Redis client
        llm_service: LLM service
        config: Optional system configuration
        
    Returns:
        Enhanced AgentOrchestrator instance
    """
    # Load system config if not provided
    if config is None:
        config = load_system_config()
    
    # Create orchestrator
    return AgentOrchestrator(agent_service, rag_service, redis_client, llm_service, config)