# Create this file as app/db/init_db.py

import asyncio
import logging
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.session import Base

# Import all models to ensure they're registered with the Base metadata
from app.db.models.tenant import Tenant
from app.db.models.user import User
from app.db.models.agent import Agent
#from app.db.models.conversation import Conversation
#from app.db.models.appointment import Appointment
from app.db.models.webhook import Webhook, WebhookLog

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_db():
    """Initialize database with required tables."""
    db_uri = str(settings.SQLALCHEMY_DATABASE_URI)  # Conversão explícita
    print(f"Connecting to: {db_uri}")  # Verifique no log
    
    try:
        engine = create_engine(db_uri)
        logger.info("Creating tables...")
        Base.metadata.create_all(bind=engine)
        logger.info("Tables created successfully!")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise

async def async_init_db():
    """Asynchronous version of database initialization."""
    async_engine = create_async_engine(settings.SQLALCHEMY_DATABASE_URI)
    
    logger.info("Creating tables asynchronously...")
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Tables created successfully!")

if __name__ == "__main__":
    logger.info("Starting database initialization...")
    init_db()
    logger.info("Database initialization completed.")