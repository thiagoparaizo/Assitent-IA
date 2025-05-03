# Atualizar o arquivo app/core/config.py

from typing import List, Union

from pydantic import AnyHttpUrl, PostgresDsn, validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "Assistant API"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = True
    
    # Segurança
    SECRET_KEY: str = "your-secret-key-here-2025-abc"  # Alterar em produção!
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 dias
    #LOGIN_DISABLED: bool = True # TODO ajustar
    
    # CORS
    CORS_ORIGINS: List[Union[str, AnyHttpUrl]] = ["http://localhost:3000", "http://localhost:5000"]
    
    # Banco de dados
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: str = "5432"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "assistant"
    SQLALCHEMY_DATABASE_URI: PostgresDsn = None
    
    # Serviço WhatsApp
    WHATSAPP_SERVICE_URL: str = "http://localhost:8080"
    WHATSAPP_SERVICE_AUTH_USERNAME: str = ""
    WHATSAPP_SERVICE_AUTH_PASSWORD: str = ""
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # RAG
    VECTOR_DB_PATH: str = "./storage/vectordb"
    
    # LLMs API_KEYs
    OPENAI_API_KEY: str = ""
    
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