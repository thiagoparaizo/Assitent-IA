# app/services/llm/gemini_service.py
from app.services.llm.base import LLMService
import google.generativeai as genai
import asyncio
from typing import List, Dict, Any

class GeminiService(LLMService):
    def __init__(self, api_key: str, model: str = "gemini-pro"):
        self.api_key = api_key
        self.model = model
        genai.configure(api_key=api_key)
        
    async def generate_response(self, messages: List[Dict[str, str]], **kwargs) -> str:
        # Converter formato de mensagens para Gemini
        gemini_messages = self._convert_to_gemini_format(messages)
        
        # Executar em thread para não bloquear
        loop = asyncio.get_event_loop()
        model = genai.GenerativeModel(self.model)
        response = await loop.run_in_executor(
            None, 
            lambda: model.generate_content(gemini_messages).text
        )
        
        return response
        
    async def generate_with_functions(self, messages: List[Dict[str, str]], 
                                    functions: List[Dict[str, Any]], 
                                    function_call: str = "auto") -> Dict[str, Any]:
        # Gemini tem uma implementação diferente de function calling
        # Implementar adaptador para o formato da Gemini
        pass
        
    async def get_embeddings(self, text: str) -> List[float]:
        # Usar modelo de embedding da Gemini
        loop = asyncio.get_event_loop()
        embedding_model = "embedding-001"  # Modelo Gemini para embeddings
        response = await loop.run_in_executor(
            None,
            lambda: genai.embed_content(model=embedding_model, content=text)
        )
        
        return response.embedding
        
    def _convert_to_gemini_format(self, messages: List[Dict[str, str]]):
        # Converter do formato OpenAI para Gemini
        gemini_chat = []
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            
            if role == "system":
                # Gemini não tem role "system", então adicionamos como user
                gemini_chat.append({"role": "user", "parts": [content]})
                gemini_chat.append({"role": "model", "parts": ["I understand. I'll act according to these instructions."]})
            elif role == "user":
                gemini_chat.append({"role": "user", "parts": [content]})
            elif role == "assistant":
                gemini_chat.append({"role": "model", "parts": [content]})
                
        return gemini_chat