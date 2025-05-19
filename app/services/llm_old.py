# Adicionar ao arquivo app/services/llm.py

from typing import Dict, Any, List, Optional
import httpx

class LLMServiceOld:
    """Serviço para geração de texto com LLMs."""
    
    def __init__(self, api_key: str, model: str = "gpt-4"):
        self.api_key = api_key
        self.model = model
        
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