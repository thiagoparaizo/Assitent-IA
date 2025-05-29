# app/services/llm/base.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple

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
    
    @abstractmethod
    async def count_tokens(self, text: str) -> int:
       """Conta tokens em um texto."""
       pass
   
    async def generate_response_with_audio(
        self, 
        messages: List[Dict[str, str]], 
        audio_data: Dict[str, Any], 
        **kwargs
    ) -> Tuple[str, Dict[str, int]]:
        """
        Gera uma resposta com suporte a áudio.
        Implementação padrão delega para generate_response (sem áudio).
        """
        return await self.generate_response(messages, **kwargs)
    
    async def get_audio_transcription(self, audio_data: Dict[str, Any]) -> Optional[str]:
        """Obtém a transcrição de um áudio (implementação opcional)."""
        return None
    
    def supports_audio(self) -> bool:
        """Indica se este serviço suporta processamento de áudio."""
        return False