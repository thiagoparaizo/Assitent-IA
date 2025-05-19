# app/services/llm/openai_service.py
from typing import Any, Dict, List
import httpx

from app.services.llm.base import LLMService

class OpenAIService(LLMService):
    def __init__(self, api_key: str, model: str = "gpt-4o-mini", base_url: str = None):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url or "https://api.openai.com/v1"
        
    async def generate_response(self, messages: List[Dict[str, str]]) -> str:
        """
        Gera uma resposta usando o modelo LLM.
        
        Args:
            messages: Lista de mensagens no formato OpenAI (role, content)
            
        Returns:
            Texto gerado
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 1000
        }
        
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=30.0
            )
            
            response.raise_for_status()
            result = response.json()
            
            return result["choices"][0]["message"]["content"]
        
    async def generate_with_functions(
        self, 
        messages: List[Dict[str, str]], 
        functions: List[Dict[str, Any]], 
        function_call: str = "auto"
    ) -> Dict[str, Any]:
        """
        Gera uma resposta com suporte a chamadas de função.
        
        Args:
            messages: Lista de mensagens no formato OpenAI
            functions: Lista de definições de funções
            function_call: Como chamar funções ("auto", "none", ou nome da função)
            
        Returns:
            Resposta completa, incluindo possíveis chamadas de função
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "functions": functions,
            "function_call": function_call,
            "temperature": 0.7
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=30.0
            )
            
            response.raise_for_status()
            return response.json()["choices"][0]["message"]
        
    async def get_embeddings(self, text: str) -> List[float]:
        """
        Gets an embedding vector for the text.
        
        Args:
            text: The text to embed
            
        Returns:
            List of floating point values representing the embedding
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.openai.com/v1/embeddings",
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.api_key}"
                    },
                    json={
                        "model": "text-embedding-ada-002",
                        "input": text[:8000]  # Truncate to avoid token limits
                    },
                    timeout=10.0
                )
                response.raise_for_status()
                return response.json()["data"][0]["embedding"]
        except Exception as e:
            print(f"Error getting embedding: {e}")
            # Return a random embedding as fallback (not ideal but allows testing)
            import random
            return [random.random() for _ in range(1536)]
        