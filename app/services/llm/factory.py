# app/services/llm/factory.py
import os
from typing import Dict, Any, Optional, Union
from app.db.models.tenant import Tenant
from app.services.llm.base import LLMService
from app.services.llm.openai_service import OpenAIService
from app.services.llm.gemini_service import GeminiService
from app.services.llm.deepseek_service import DeepSeekService
from app.db.models.llm_provider import LLMProvider
from app.db.models.llm_model import LLMModel

from sqlalchemy.orm import Session
import logging


logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("app.services.llm.factory")

class LLMServiceFactory:
    """Factory para criar instâncias de serviços LLM."""
    
    @staticmethod
    async def create_service(db, tenant_id: Optional[Union[int, str]] = None, 
                        provider_id: Optional[int] = None,
                        model_id: Optional[int] = None) -> LLMService:
        """
        Cria um serviço LLM com base nas configurações do tenant ou parâmetros.
        """
        provider = None
        model = None
        api_key = None
        
        print(f"[DEBUG] LLMServiceFactory.create_service: tenant_id: {tenant_id}, provider_id: {provider_id}, model_id: {model_id}")
        
        # Verificar se db é uma instância de Session e não Depends
        if not isinstance(db, Session):
            logger.error(f"Parâmetro db inválido: {type(db)}")
            return OpenAIService(api_key=get_api_key_for_provider("openai"))
            
        # Converter tenant_id para int se for string
        if isinstance(tenant_id, str) and tenant_id.isdigit():
            tenant_id = int(tenant_id)
        
        # Obter configurações do tenant (se especificado)
        if tenant_id:
            try:
                tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
                if tenant:
                    # Usar configurações específicas do tenant
                    if tenant.default_llm_model_id:
                        model = db.query(LLMModel).filter(LLMModel.id == tenant.default_llm_model_id).first()
                        provider = model.provider if model else None
                    elif tenant.default_llm_provider_id:
                        provider = db.query(LLMProvider).filter(LLMProvider.id == tenant.default_llm_provider_id).first()
                        model = db.query(LLMModel).filter(
                            LLMModel.provider_id == provider.id, 
                            LLMModel.is_active == True
                        ).first() if provider else None
                    
                    # Usar API key específica do tenant ou a global
                    if provider:
                        api_key = tenant.llm_api_key or get_api_key_for_provider(provider.provider_type)
                    else:
                        # Se não houver provider, usar a OpenAI como fallback
                        api_key = tenant.llm_api_key or get_api_key_for_provider("openai")
            except Exception as e:
                logger.error(f"Erro ao obter configurações do tenant {tenant_id}: {e}")
                logger.exception(e)
        
        # Sobrepor com provider_id e model_id se especificados
        if provider_id:
            # Obter configurações do provider
            print(f"[DEBUG] LLMServiceFactory.create_service: provider_id: {provider_id}")
            try:
                provider = db.query(LLMProvider).filter(LLMProvider.id == provider_id).first()
                if provider:
                    # Usar configurações do provider
                    print(f"[DEBUG] LLMServiceFactory.create_service: usando configurações do provider: {provider}")
                    model = db.query(LLMModel).filter(
                        LLMModel.provider_id == provider.id, 
                        LLMModel.is_active == True
                    ).first()
                    api_key = get_api_key_for_provider(provider.provider_type)
                    print(f"[DEBUG] LLMServiceFactory.create_service: usando configurações do provider: {provider} model: {model}")
                    print(f"[DEBUG] LLMServiceFactory.create_service: usando configurações do provider: {provider} api_key: {api_key[-10:]}")
            except Exception as e:
                logger.error(f"Erro ao obter provider {provider_id}: {e}")
        
        if model_id:
            # Obter configurações do model
            print(f"[DEBUG] LLMServiceFactory.create_service: model_id: {model_id}")
            try:
                model = db.query(LLMModel).filter(LLMModel.id == model_id).first()
                if model:
                    provider = model.provider
                    print(f"[DEBUG] LLMServiceFactory.create_service: usando configurações do model: {model}")
                    api_key = get_api_key_for_provider(provider.provider_type) if provider else get_api_key_for_provider("openai")
                    print(f"[DEBUG] LLMServiceFactory.create_service: usando configurações do model: {model} api_key: {api_key[-10:]}")
            except Exception as e:
                logger.error(f"Erro ao obter model {model_id}: {e}")
        
        # Criar serviço adequado
        if not provider or not model:
            # Fallback para OpenAI
            logger.info("Using OpenAI as fallback LLM service")
            print("[DEBUG] LLMServiceFactory.create_service: Using OpenAI as fallback LLM service")
            return OpenAIService(api_key=get_api_key_for_provider("openai"))
        
        try:
            if provider.provider_type == "openai":
                logger.info(f"Creating OpenAI service with model {model.model_id}")
                return OpenAIService(
                    api_key=api_key, 
                    model=model.model_id, 
                    base_url=provider.base_url
                )
            elif provider.provider_type == "gemini":
                logger.info(f"Creating Gemini service with model {model.model_id}")
                return GeminiService(
                    api_key=api_key, 
                    model=model.model_id
                )
            elif provider.provider_type == "deepseek":
                logger.info(f"Creating DeepSeek service with model {model.model_id}")
                return DeepSeekService(
                    api_key=api_key, 
                    model=model.model_id, 
                    base_url=provider.base_url
                )
            else:
                logger.warning(f"Unknown provider type: {provider.provider_type}, falling back to OpenAI")
                # Fallback para OpenAI
                return OpenAIService(api_key=get_api_key_for_provider("openai"))
        except Exception as e:
            logger.error(f"Erro ao criar serviço LLM: {e}")
            return OpenAIService(api_key=get_api_key_for_provider("openai"))

def get_api_key_for_provider(provider_type: str) -> str:
    """Obtém a chave API global para um tipo de provedor."""
    if provider_type == "openai":
        return os.getenv("OPENAI_API_KEY", "")
    elif provider_type == "gemini":
        return os.getenv("GEMINI_API_KEY", "")
    elif provider_type == "deepseek":
        return os.getenv("DEEPSEEK_API_KEY", "")
    else:
        logger.warning(f"Unknown provider type for API key: {provider_type}")
        return ""