import json
import logging
from typing import Any, Dict, List, Optional, Union

import httpx
from fastapi import HTTPException

from app.core.config import settings

logger = logging.getLogger(__name__)


class WhatsAppService:
    """
    Serviço para integração com o serviço WhatsApp em Go
    """
    
    def __init__(self, base_url: str = None, auth_username: str = None, auth_password: str = None):
        self.base_url = base_url or settings.WHATSAPP_SERVICE_URL
        self.auth_username = auth_username or settings.WHATSAPP_SERVICE_AUTH_USERNAME
        self.auth_password = auth_password or settings.WHATSAPP_SERVICE_AUTH_PASSWORD
        self.auth = None
        
        if self.auth_username and self.auth_password:
            self.auth = (self.auth_username, self.auth_password)
    
    async def _request(self, method: str, path: str, data: dict = None, params: dict = None) -> dict:
        """
        Executa uma requisição para o serviço WhatsApp
        """
        url = f"{self.base_url}/{path.lstrip('/')}"
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.request(
                    method=method,
                    url=url,
                    json=data,
                    params=params,
                    auth=self.auth,
                    timeout=30.0
                )
                
                response.raise_for_status()
                logger.debug(f"Resposta do serviço WhatsApp: {response.text}")
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Erro HTTP ao acessar o serviço WhatsApp: {e}")
            print(f"Erro HTTP ao acessar o serviço WhatsApp: {e}")  
            try:
                error_detail = e.response.json().get("error", str(e))
            except:
                error_detail = str(e)
            
            raise HTTPException(status_code=e.response.status_code, detail=error_detail)
        except httpx.RequestError as e:
            logger.error(f"Erro de requisição ao acessar o serviço WhatsApp: {e}")
            print(f"Erro de requisição ao acessar o serviço WhatsApp: {e}")
            raise HTTPException(status_code=503, detail=f"Serviço WhatsApp indisponível: {str(e)}")
        
        except Exception as e:
            logger.error(f"Erro inesperado ao acessar o serviço WhatsApp: {e}")
            print(f"Erro inesperado ao acessar o serviço WhatsApp: {e}")
            raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")
    
    # Endpoints de dispositivos
    
    async def get_devices(self, tenant_id: int) -> List[dict]:
        """Obtém a lista de dispositivos de um tenant"""
        devices = await self._request("GET", "/api/devices", params={"tenant_id": tenant_id})
        return [self._adapt_device(device) for device in devices]

    async def get_device(self, device_id: int) -> dict:
        """Obtém informações de um dispositivo específico"""
        device = await self._request("GET", f"/api/devices/{device_id}")
        return self._adapt_device(device)
    
    async def create_device(self, tenant_id: int, name: str, description: str, phone_number: str) -> dict:
        """Cria um novo dispositivo"""
        data = {
            "tenant_id": tenant_id,
            "name": name,
            "description": description,
            "phone_number": phone_number
        }
        return await self._request("POST", "/api/devices", data=data)
    
    async def update_device_status(self, device_id: int, status: str) -> dict:
        """Atualiza o status de um dispositivo"""
        data = {"status": status}
        return await self._request("PUT", f"/api/devices/{device_id}/status", data=data)
    
    async def get_device_status(self, device_id: int) -> dict:
        """Obtém o status atual de um dispositivo"""
        status = await self._request("GET", f"/api/devices/{device_id}/status")
        return {
            "id": status.get("id"),
            "status": status.get("status"),
            "connected": status.get("connected"),
            "requires_reauth": status.get("requires_reauth"),
            "last_seen": status.get("last_seen", {}).get("Time") if status.get("last_seen", {}).get("Valid") else None
        }
    
    async def get_qr_code(self, device_id: int) -> dict:
        """Obtém o QR code para vincular um dispositivo"""
        return await self._request("GET", f"/api/devices/{device_id}/qrcode")
    
    async def disconnect_device(self, device_id: int) -> dict:
        """Desconecta um dispositivo"""
        return await self._request("POST", f"/api/devices/{device_id}/disconnect")
    
    # Endpoints de mensagens
    
    async def send_message(self, device_id: int, to: str, message: str) -> dict:
        """Envia uma mensagem de texto"""
        data = {"to": to, "message": message}
        return await self._request("POST", f"/api/devices/{device_id}/send", data=data)
    
    async def send_group_message(self, device_id: int, group_id: str, message: str) -> dict:
        """Envia uma mensagem para um grupo"""
        data = {"message": message}
        return await self._request("POST", f"/api/devices/{device_id}/group/{group_id}/send", data=data)
    
    # Endpoints de contatos e grupos
    
    async def get_contacts(self, device_id: int) -> dict:
        """Obtém a lista de contatos"""
        return await self._request("GET", f"/api/devices/{device_id}/contacts")
    
    async def get_groups(self, device_id: int) -> List[dict]:
        """Obtém a lista de grupos"""
        return await self._request("GET", f"/api/devices/{device_id}/groups")
    
    # Endpoints de mensagens
    
    async def get_contact_messages(self, device_id: int, contact_id: str, filter: str = "day") -> List[Dict[str, Any]]:
        """
        Obtém mensagens de um contato específico
        """
        try:
            messages = await self._request(
                "GET", 
                f"/api/devices/{device_id}/contact/{contact_id}/messages", 
                params={"filter": filter}
            )
            
            # Se a resposta for null, retornar uma lista vazia
            if messages is None:
                return []
            
            return messages
        except Exception as e:
            print(f"Erro ao obter mensagens do contato: {e}")
            return []
    
    async def get_group_messages(self, device_id: int, group_id: str, filter: str = "day") -> List[Dict[str, Any]]:
        """
        Obtém mensagens de um grupo específico
        """
        try:
            messages = await self._request(
                "GET", 
                f"/api/devices/{device_id}/group/{group_id}/messages", 
                params={"filter": filter}
            )
            
            # Se a resposta for null, retornar uma lista vazia
            if messages is None:
                return []
            
            return messages
        except Exception as e:
            print(f"Erro ao obter mensagens do grupo: {e}")
            return []
    
    # Endpoints de tracked entities
    
    async def get_tracked_entities(self, device_id: int) -> List[Dict[str, Any]]:
        """
        Obtém a lista de entidades rastreadas
        """
        try:
            entities = await self._request(
                "GET", 
                f"/api/devices/{device_id}/tracked"
            )
            return entities
        except Exception as e:
            logger.error(f"Erro ao obter entidades rastreadas: {e}")
            print(f"Erro ao obter entidades rastreadas: {e}")
        # Retornar uma lista vazia em caso de erro para evitar crash
        return []
    
    async def set_tracked_entity(
        self, 
        device_id: int, 
        jid: str, 
        is_tracked: bool = True,
        track_media: bool = True,
        allowed_media_types: List[str] = None
    ) -> dict:
        """Configura uma entidade para ser rastreada"""
        data = {
            "jid": jid,
            "is_tracked": is_tracked,
            "track_media": track_media,
            "allowed_media_types": allowed_media_types or ["image", "audio", "video", "document"]
        }
        return await self._request("POST", f"/api/devices/{device_id}/tracked", data=data)
    
    async def delete_tracked_entity(self, device_id: int, jid: str) -> dict:
        """Remove uma entidade rastreada"""
        return await self._request("DELETE", f"/api/devices/{device_id}/tracked/{jid}")
    
    def _adapt_device(self, device_data: dict) -> dict:
        """Adapta os campos do dispositivo do formato Go para o formato Python"""
        return {
            "id": device_data.get("ID"),
            "tenant_id": device_data.get("TenantID"),
            "name": device_data.get("Name"),
            "description": device_data.get("Description"),
            "phone_number": device_data.get("PhoneNumber"),
            "status": device_data.get("Status"),
            "jid": device_data.get("JID", {}).get("String") if device_data.get("JID", {}).get("Valid") else None,
            "created_at": device_data.get("CreatedAt"),
            "updated_at": device_data.get("UpdatedAt"),
            "last_seen": device_data.get("LastSeen", {}).get("Time") if device_data.get("LastSeen", {}).get("Valid") else None,
            "requires_reauth": device_data.get("RequiresReauth", False)
        }

