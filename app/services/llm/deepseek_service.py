# app/services/llm/deepseek_service.py
from typing import Dict, List
from app.services.llm.base import LLMService
import httpx

class DeepSeekService(LLMService):
    def __init__(self, api_key: str, model: str = "deepseek-chat", base_url: str = None):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url or "https://api.deepseek.com/v1"
        
    async def generate_response(self, messages: List[Dict[str, str]], **kwargs) -> str:
        # DeepSeek geralmente usa uma API compatível com OpenAI
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": kwargs.get("temperature", 0.7),
                    "max_tokens": kwargs.get("max_tokens", 1000)
                },
                timeout=30.0
            )
            
            response.raise_for_status()
            result = response.json()
            
            return result["choices"][0]["message"]["content"]
            
    # Implementar outras funções...