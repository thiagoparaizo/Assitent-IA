# app/services/llm/base.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class LLMService(ABC):
    """Interface abstrata para serviços LLM."""
    
    @abstractmethod
    async def generate_response(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Gera uma resposta a partir de mensagens."""
        pass
    
    @abstractmethod
    async def generate_with_functions(self, messages: List[Dict[str, str]], 
                                    functions: List[Dict[str, Any]], 
                                    function_call: str = "auto") -> Dict[str, Any]:
        """Gera uma resposta com suporte a chamadas de função."""
        pass
    
    @abstractmethod
    async def get_embeddings(self, text: str) -> List[float]:
        """Obtém embeddings para um texto."""
        pass