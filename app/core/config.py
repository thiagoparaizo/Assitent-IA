# Atualizar o arquivo app/core/config.py

import os
from typing import List, Union

from pydantic import AnyHttpUrl, PostgresDsn, validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = os.getenv("PROJECT_NAME", "AI Assistant API")
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = os.getenv("DEBUG","false").lower() == "true"
    
    # Segurança
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here-2025-abc")  # Alterar em produção!
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 dias
    
    # CORS
    CORS_ORIGINS: List[Union[str, AnyHttpUrl]] = ["http://localhost:3000", "http://localhost:5000"]
    
    # Banco de dados
    POSTGRES_SERVER: str = os.getenv("POSTGRES_SERVER", "localhost")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "5432")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "postgres")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "assistant")
    SQLALCHEMY_DATABASE_URI: PostgresDsn = None
    
    # Serviço WhatsApp
    WHATSAPP_SERVICE_URL: str = os.getenv("WHATSAPP_SERVICE_URL", "http://localhost:8080")
    WHATSAPP_SERVICE_AUTH_USERNAME: str = os.getenv("WHATSAPP_SERVICE_AUTH_USERNAME", "")
    WHATSAPP_SERVICE_AUTH_PASSWORD: str = os.getenv("WHATSAPP_SERVICE_AUTH_PASSWORD", "")
    
    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # RAG
    VECTOR_DB_PATH: str = os.getenv("VECTOR_DB_PATH", "./storage/vectordb")
    
    # Memory
    MEMORY_DB_PATH: str = os.getenv("MEMORY_DB_PATH", "./storage/memorydb")
    MEMORY_ENABLED: bool = os.getenv("MEMORY_ENABLED", "true").lower() == "true"
    MEMORY_USE_LOCAL_STORAGE: bool = os.getenv("MEMORY_USE_LOCAL_STORAGE", "true").lower() == "true"
    

    # LLMs API_KEYs
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    # Modelo LLM para conversão de Audio
    LLM_MODEL_FOR_AUDIO: str = os.getenv("LLM_MODEL_FOR_AUDIO", "gemini-2.0-flash")
    
    #Email config
    EMAIL_FROM: str = os.getenv("EMAIL_FROM", "no-reply@yourdomain.com")
    SMTP_SERVER: str = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT: int = os.getenv("SMTP_PORT", 587)
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_TLS: bool = os.getenv("SMTP_TLS", "true").lower() == "true"
    
    # Configurações de áudio
    AUDIO_MAX_SIZE_MB: int = os.getenv("AUDIO_MAX_SIZE_MB", 10)  # Tamanho máximo em MB # TODO verificar 
    AUDIO_SUPPORTED_FORMATS: List[str] = ["mp3", "ogg", "wav"]
    AUDIO_PROCESSING_TIMEOUT: int = os.getenv("AUDIO_PROCESSING_TIMEOUT", 30)  # Timeout em segundos

    
    @validator("SQLALCHEMY_DATABASE_URI", pre=True)
    def assemble_db_connection(cls, v: str, values: dict) -> str:
        if isinstance(v, str):
            return v
        
        return PostgresDsn.build(
            scheme="postgresql",
            username=values.get("POSTGRES_USER"),
            password=values.get("POSTGRES_PASSWORD"),
            host=values.get("POSTGRES_SERVER"),
            port=values.get("POSTGRES_PORT"),
            path=f"/{values.get('POSTGRES_DB', '')}",
        )
        
    @validator("SQLALCHEMY_DATABASE_URI", pre=True)
    def assemble_db_connection(cls, v: str, values: dict) -> str:
        if isinstance(v, str):
            return v
        
        port = int(values.get("POSTGRES_PORT", 5432))
        db_name = values.get("POSTGRES_DB", "")
        
        # Construa manualmente a URL para ter controle total
        db_uri = (
            f"postgresql://{values['POSTGRES_USER']}:{values['POSTGRES_PASSWORD']}"
            f"@{values['POSTGRES_SERVER']}:{port}/{db_name}"
        )
        
        print("SQLALCHEMY_DATABASE_URI:", db_uri)
        
        # Valide com PostgresDsn mas retorne como string
        return str(PostgresDsn(db_uri))
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()