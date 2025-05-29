# app/services/llm/deepseek_service.py
from typing import Any, Dict, List, Tuple
import httpx
import asyncio
import logging
import tiktoken

from app.services.llm.base import LLMService

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("app.services.llm.deepseek_service")

class DeepSeekService(LLMService):
    def __init__(self, api_key: str, model: str = "deepseek-chat", base_url: str = None):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url or "https://api.deepseek.com/v1"
        
        # DeepSeek usa tokenizer similar ao GPT
        try:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
        except Exception as e:
            logger.warning(f"Failed to load tokenizer: {e}")
            self.tokenizer = None
            
    def supports_audio(self) -> bool:
        """OpenAI não suporta processamento de áudio nesta implementação."""
        return False

    async def count_tokens(self, text: str) -> int:
        """
        Conta tokens em um texto usando o tokenizer apropriado.
        """
        if self.tokenizer:
            try:
                return len(self.tokenizer.encode(text))
            except Exception as e:
                logger.warning(f"Error counting tokens: {e}")
        
        # Fallback para estimativa
        return max(1, len(text) // 4)

    async def generate_response(self, messages: List[Dict[str, str]], **kwargs) -> Tuple[str, Dict[str, int]]:
        """
        Gera uma resposta usando DeepSeek e retorna o texto gerado e informações de uso de tokens.
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        # Preparar payload seguindo a API do DeepSeek
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 1000),
            "top_p": kwargs.get("top_p", 0.95),
            "frequency_penalty": kwargs.get("frequency_penalty", 0.0),
            "presence_penalty": kwargs.get("presence_penalty", 0.0),
            "stream": False
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=60.0  # DeepSeek pode ser mais lento
                )
                
                response.raise_for_status()
                result = response.json()
                
                # Extrair informações de uso de tokens
                token_usage = {
                    "prompt_tokens": result.get("usage", {}).get("prompt_tokens", 0),
                    "completion_tokens": result.get("usage", {}).get("completion_tokens", 0),
                    "total_tokens": result.get("usage", {}).get("total_tokens", 0)
                }
                
                # Se a API não retornar informações de tokens, calcular manualmente
                if token_usage["prompt_tokens"] == 0:
                    prompt_tokens = 0
                    for message in messages:
                        prompt_tokens += await self.count_tokens(message.get("content", ""))
                    token_usage["prompt_tokens"] = prompt_tokens
                    
                    # Contar tokens na resposta
                    content = result["choices"][0]["message"]["content"]
                    completion_tokens = await self.count_tokens(content)
                    token_usage["completion_tokens"] = completion_tokens
                    
                    # Calcular total
                    token_usage["total_tokens"] = prompt_tokens + completion_tokens
                
                return result["choices"][0]["message"]["content"], token_usage
                
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error from DeepSeek API: {e}")
            error_msg = f"Erro na API DeepSeek: {e.response.status_code}"
            
            # Tentar extrair detalhes do erro
            try:
                error_detail = e.response.json()
                if "error" in error_detail:
                    error_msg = f"DeepSeek API Error: {error_detail['error'].get('message', str(e))}"
            except:
                pass
            
            token_usage = {
                "prompt_tokens": 0,
                "completion_tokens": await self.count_tokens(error_msg),
                "total_tokens": await self.count_tokens(error_msg)
            }
            return error_msg, token_usage
            
        except httpx.RequestError as e:
            logger.error(f"Request error to DeepSeek API: {e}")
            error_msg = f"Erro de conexão com DeepSeek: {str(e)}"
            token_usage = {
                "prompt_tokens": 0,
                "completion_tokens": await self.count_tokens(error_msg),
                "total_tokens": await self.count_tokens(error_msg)
            }
            return error_msg, token_usage
            
        except Exception as e:
            logger.error(f"Unexpected error with DeepSeek API: {e}")
            error_msg = f"Erro inesperado: {str(e)}"
            token_usage = {
                "prompt_tokens": 0,
                "completion_tokens": await self.count_tokens(error_msg),
                "total_tokens": await self.count_tokens(error_msg)
            }
            return error_msg, token_usage

    async def generate_with_functions(
        self, 
        messages: List[Dict[str, str]], 
        functions: List[Dict[str, Any]], 
        function_call: str = "auto"
    ) -> Tuple[Dict[str, Any], Dict[str, int]]:
        """
        Gera uma resposta com suporte a chamadas de função usando DeepSeek.
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        # Preparar payload com funções
        payload = {
            "model": self.model,
            "messages": messages,
            "functions": functions,
            "function_call": function_call,
            "temperature": 0.7,
            "max_tokens": 1000,
            "stream": False
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=60.0
                )
                
                response.raise_for_status()
                result = response.json()
                
                # Extrair informações de uso de tokens
                token_usage = {
                    "prompt_tokens": result.get("usage", {}).get("prompt_tokens", 0),
                    "completion_tokens": result.get("usage", {}).get("completion_tokens", 0),
                    "total_tokens": result.get("usage", {}).get("total_tokens", 0)
                }
                
                # Calcular tokens se não fornecidos pela API
                if token_usage["prompt_tokens"] == 0:
                    prompt_tokens = 0
                    for message in messages:
                        prompt_tokens += await self.count_tokens(message.get("content", ""))
                    
                    # Adicionar tokens das funções (aproximado)
                    functions_text = str(functions)
                    prompt_tokens += await self.count_tokens(functions_text)
                    
                    token_usage["prompt_tokens"] = prompt_tokens
                    
                    # Contar tokens na resposta
                    message_content = str(result["choices"][0]["message"])
                    completion_tokens = await self.count_tokens(message_content)
                    token_usage["completion_tokens"] = completion_tokens
                    
                    # Calcular total
                    token_usage["total_tokens"] = prompt_tokens + completion_tokens
                
                return result["choices"][0]["message"], token_usage
                
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error from DeepSeek API (functions): {e}")
            error_response = {
                "role": "assistant", 
                "content": f"Erro na API DeepSeek: {e.response.status_code}"
            }
            
            # Tentar extrair detalhes do erro
            try:
                error_detail = e.response.json()
                if "error" in error_detail:
                    error_response["content"] = f"DeepSeek API Error: {error_detail['error'].get('message', str(e))}"
            except:
                pass
            
            token_usage = {
                "prompt_tokens": 0,
                "completion_tokens": await self.count_tokens(error_response["content"]),
                "total_tokens": await self.count_tokens(error_response["content"])
            }
            return error_response, token_usage
            
        except Exception as e:
            logger.error(f"Unexpected error with DeepSeek API (functions): {e}")
            error_response = {
                "role": "assistant", 
                "content": f"Erro inesperado: {str(e)}"
            }
            token_usage = {
                "prompt_tokens": 0,
                "completion_tokens": await self.count_tokens(error_response["content"]),
                "total_tokens": await self.count_tokens(error_response["content"])
            }
            return error_response, token_usage

    async def get_embeddings(self, text: str) -> List[float]:
        """
        Obtém embeddings usando a API de embeddings do DeepSeek.
        Nota: DeepSeek pode não ter API de embeddings dedicada, então usamos uma abordagem alternativa.
        """
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            # Tentar usar endpoint de embeddings se disponível
            payload = {
                "model": "deepseek-embedding",  # Modelo hipotético
                "input": text[:8000]  # Truncar para evitar limites
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/embeddings",
                    headers=headers,
                    json=payload,
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return result["data"][0]["embedding"]
                else:
                    # Se não há API de embeddings, usar abordagem alternativa
                    raise httpx.HTTPStatusError("Embeddings not available", request=response.request, response=response)
                    
        except Exception as e:
            logger.warning(f"DeepSeek embeddings not available, using fallback: {e}")
            
            # Fallback: usar uma abordagem simples baseada em hash
            # Em produção, você poderia usar outro serviço de embeddings
            return self._generate_simple_embedding(text)

    def _generate_simple_embedding(self, text: str) -> List[float]:
        """
        Gera um embedding simples baseado em características do texto.
        Esta é uma implementação básica para fallback.
        """
        import hashlib
        import struct
        
        # Criar um hash do texto
        text_hash = hashlib.md5(text.encode()).digest()
        
        # Converter hash em números float
        embedding = []
        for i in range(0, len(text_hash), 4):
            chunk = text_hash[i:i+4]
            if len(chunk) == 4:
                # Converter 4 bytes em um float
                float_val = struct.unpack('f', chunk)[0]
                # Normalizar para [-1, 1]
                normalized = max(-1.0, min(1.0, float_val / 1e10))
                embedding.append(normalized)
        
        # Preencher até 1536 dimensões (compatível com OpenAI)
        while len(embedding) < 1536:
            # Usar características do texto para preencher
            char_sum = sum(ord(c) for c in text[:100])  # Primeiros 100 chars
            normalized_char = (char_sum % 1000) / 500.0 - 1.0  # Normalizar para [-1, 1]
            embedding.append(normalized_char)
        
        # Truncar se necessário
        return embedding[:1536]

    async def test_connection(self) -> bool:
        """
        Testa a conexão com a API DeepSeek.
        """
        try:
            test_messages = [{"role": "user", "content": "Hello"}]
            response, _ = await self.generate_response(test_messages, max_tokens=5)
            return not response.startswith("Erro")
        except Exception as e:
            logger.error(f"DeepSeek connection test failed: {e}")
            return False

    def get_model_info(self) -> Dict[str, Any]:
        """
        Retorna informações sobre o modelo DeepSeek configurado.
        """
        return {
            "provider": "deepseek",
            "model": self.model,
            "base_url": self.base_url,
            "supports_functions": True,
            "supports_streaming": False,  # Pode ser implementado se necessário
            "max_tokens": 4096,  # Valor típico para DeepSeek
            "context_window": 32768  # Contexto típico do DeepSeek
        }
    
    async def generate_response_with_audio(
        self, 
        messages: List[Dict[str, str]], 
        audio_data: Dict[str, Any], 
        **kwargs
    ) -> Tuple[str, Dict[str, int]]:
        """
        OpenAI não suporta áudio, então ignora e processa apenas texto.
        """
        return await self.generate_response(messages, **kwargs)