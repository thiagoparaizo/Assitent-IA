from fastapi import APIRouter

from app.api.endpoints import auth, whatsapp, tenants, conversations, appointments, webhook, knowledge, agents, internal

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(whatsapp.router, prefix="/whatsapp", tags=["whatsapp"])
api_router.include_router(tenants.router, prefix="/tenants", tags=["tenants"])
#api_router.include_router(conversations.router, prefix="/conversations", tags=["conversas"])
#api_router.include_router(appointments.router, prefix="/appointments", tags=["agendamentos"])
api_router.include_router(webhook.router, prefix="/webhook", tags=["webhook"])
api_router.include_router(knowledge.router, prefix="/knowledge", tags=["conhecimento"])
api_router.include_router(agents.router, prefix="/agents", tags=["agentes"])
api_router.include_router(internal.router, prefix="/internal", tags=["internal"])

@api_router.get("/health", tags=["health"])
def health_check():
    return {"status": "healthy", "version": "0.1.0"}