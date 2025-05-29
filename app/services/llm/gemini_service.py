# app/services/llm/gemini_service.py
import base64
from typing import Any, Dict, List, Optional, Tuple
import google.generativeai as genai
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
import time

from app.services.llm.base import LLMService

logger = logging.getLogger(__name__)

class GeminiService(LLMService):
    def __init__(self, api_key: str, model: str = "gemini-1.5-flash", base_url: str = None):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url  # Gemini não usa base_url customizada, mas mantemos para compatibilidade
        
        # Configure Gemini
        genai.configure(api_key=api_key)
        print(f"Gemini configurado com sucesso. API Key: {api_key[-10:]}")
        
        # Configurações de segurança permissivas para uso comercial
        self.safety_settings = [
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_ONLY_HIGH"
            },
            {
                "category": "HARM_CATEGORY_HATE_SPEECH",
                "threshold": "BLOCK_ONLY_HIGH"
            },
            {
                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "threshold": "BLOCK_ONLY_HIGH"
            },
            {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_ONLY_HIGH"
            }
        ]
        
        # Para contagem de tokens (aproximada)
        self._executor = ThreadPoolExecutor(max_workers=4)
        
    def supports_audio(self) -> bool:
        """Gemini suporta processamento de áudio."""
        return True

    async def count_tokens(self, text: str) -> int:
        """
        Conta tokens em um texto usando estimativa baseada em caracteres.
        O Gemini não tem um tokenizer público, então usamos aproximação.
        """
        try:
            # Aproximação: ~4 caracteres por token (similar ao GPT)
            # Ajustamos para ser um pouco mais conservador
            return max(1, len(text) // 3)
        except Exception as e:
            logger.warning(f"Error counting tokens: {e}")
            return len(text) // 4  # Fallback mais simples

    async def generate_response(self, messages: List[Dict[str, str]], **kwargs) -> Tuple[str, Dict[str, int]]:
        """
        Gera uma resposta usando o Gemini e retorna o texto gerado e informações de uso de tokens.
        """
        print(f"[DEBUG] GeminiService.generate_response: messages: {messages}")
        try:
            # Converter mensagens para o formato do Gemini
            gemini_messages = self._convert_to_gemini_format(messages)
            print(f"[DEBUG] GeminiService.generate_response: gemini_messages: {gemini_messages}")
            
            # Configurações de geração
            generation_config = {
                "temperature": kwargs.get("temperature", 0.7),
                "max_output_tokens": kwargs.get("max_tokens", 1000),
                "top_p": kwargs.get("top_p", 0.8),
                "top_k": kwargs.get("top_k", 40)
            }
            
            # Executar geração em thread separada para evitar bloqueio
            loop = asyncio.get_event_loop()
            try:
                response = await loop.run_in_executor(
                    self._executor,
                    self._generate_sync,
                    gemini_messages,
                    generation_config
                )
            except Exception as e:
                print(f"[DEBUG] GeminiService.generate_response: Error setting default executor: {e}")
                logger.error(f"Error setting default executor: {e}")    
            
            
            # Calcular tokens (aproximado já que Gemini não fornece contagem exata)
            prompt_text = " ".join([msg.get("content", "") for msg in messages])
            prompt_tokens = await self.count_tokens(prompt_text)
            
            response_text = response.text if hasattr(response, 'text') else str(response)
            completion_tokens = await self.count_tokens(response_text)
            
            token_usage = {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens
            }
            
            return response_text, token_usage
            
        except Exception as e:
            logger.error(f"Error generating response with Gemini: {e}")
            # Retornar erro com informações básicas
            error_message = f"Erro ao gerar resposta: {str(e)}"
            token_usage = {
                "prompt_tokens": 0,
                "completion_tokens": await self.count_tokens(error_message),
                "total_tokens": await self.count_tokens(error_message)
            }
            return error_message, token_usage

    # async def generate_response_with_audio(
    #     self, 
    #     messages: List[Dict[str, str]], 
    #     audio_data: Dict[str, Any], 
    #     **kwargs
    # ) -> Tuple[str, Dict[str, int]]:
    #     """
    #     Gera uma resposta com suporte a áudio usando Gemini.
    #     """
    #     try:
    #         # Usar modelo que suporta áudio
    #         model = genai.GenerativeModel('gemini-2.0-flash') ## fixar modelo para audio
            
    #         # Preparar o áudio
    #         audio_base64 = audio_data.get("base64", "")
    #         if not audio_base64:
    #             return await self.generate_response(messages, **kwargs)
            
    #         # Decodificar o áudio base64
    #         audio_bytes = base64.b64decode(audio_base64)
            
    #         # Preparar conteúdo para o Gemini
    #         content_parts = []
            
    #         # CORREÇÃO: Processar mensagens corretamente
    #         system_instruction = ""
    #         user_content = ""
            
    #         for msg in messages:
    #             role = msg.get("role", "user")
    #             content = msg.get("content", "")
                
    #             if role == "system":
    #                 system_instruction += content + "\n"
    #             elif role == "user":
    #                 user_content += content + "\n"
            
    #         # Adicionar texto (instruções + mensagem do usuário)
    #         if system_instruction:
    #             content_parts.append(f"Instruções: {system_instruction}\n\nUsuário: {user_content}")
    #         else:
    #             content_parts.append(user_content)
            
    #         # Adicionar áudio
    #         content_parts.append({
    #             "mime_type": "audio/mp3",
    #             "data": audio_bytes
    #         })
            
    #         # CORREÇÃO: Configurar model com system_instruction se disponível
    #         if system_instruction:
    #             model = genai.GenerativeModel(
    #                 self.model or 'gemini-1.5-pro',
    #                 system_instruction=system_instruction
    #             )
    #             # Usar apenas o conteúdo do usuário + áudio
    #             content_parts = [user_content, {
    #                 "mime_type": "audio/mp3", 
    #                 "data": audio_bytes
    #             }]
            
    #         # Gerar resposta
    #         loop = asyncio.get_event_loop()
    #         response = await loop.run_in_executor(
    #             None, 
    #             lambda: model.generate_content(content_parts)
    #         )
            
    #         # Contagem de tokens (estimativa)
    #         token_usage = {
    #             "prompt_tokens": sum(len(msg.get("content", "").split()) for msg in messages) + 100,
    #             "completion_tokens": len(response.text.split()) if response.text else 0,
    #             "total_tokens": 0
    #         }
    #         token_usage["total_tokens"] = token_usage["prompt_tokens"] + token_usage["completion_tokens"]
            
    #         return response.text, token_usage
            
    #     except Exception as e:
    #         logger.error(f"Erro ao processar áudio com Gemini: {e}")
    #         return await self.generate_response(messages, **kwargs)

    # async def generate_response_with_audio(
    #     self, 
    #     messages: List[Dict[str, str]], 
    #     audio_data: Dict[str, Any], 
    #     **kwargs
    # ) -> Tuple[str, Dict[str, int]]:
    #     """
    #     Gera uma resposta com suporte a áudio usando Gemini.
    #     """
    #     try:
    #         # Usar modelo que suporta áudio (gemini-pro ou gemini-1.5-pro)
    #         model = genai.GenerativeModel('gemini-2.0-flash') ## fixar modelo para audio
            
    #         # Preparar o áudio
    #         audio_base64 = audio_data.get("base64", "")
    #         if not audio_base64:
    #             # Fallback para método sem áudio
    #             return await self.generate_response(messages, **kwargs)
            
    #         # Decodificar o áudio base64
    #         audio_bytes = base64.b64decode(audio_base64)
            
    #         # Preparar conteúdo para o Gemini
    #         content_parts = []
            
    #         # Adicionar mensagens de texto
    #         for msg in messages:
    #             if msg["role"] == "user":
    #                 content_parts.append(msg["content"])
            
    #         # Adicionar áudio
    #         content_parts.append({
    #             "mime_type": "audio/mp3",
    #             "data": audio_bytes
    #         })
            
    #         # Gerar resposta
    #         loop = asyncio.get_event_loop()
    #         response = await loop.run_in_executor(
    #             None, 
    #             lambda: model.generate_content(content_parts)
    #         )
            
    #         # Contagem de tokens (estimativa)
    #         token_usage = {
    #             "prompt_tokens": sum(len(msg.get("content", "").split()) for msg in messages) + 100,  # +100 para áudio
    #             "completion_tokens": len(response.text.split()) if response.text else 0,
    #             "total_tokens": 0
    #         }
    #         token_usage["total_tokens"] = token_usage["prompt_tokens"] + token_usage["completion_tokens"]
            
    #         return response.text, token_usage
            
    #     except Exception as e:
    #         logger.error(f"Erro ao processar áudio com Gemini: {e}")
    #         # Fallback para método sem áudio
    #         #return await self.generate_response(messages, **kwargs)
    #         return None, None


    async def get_audio_transcription(self, audio_data: Dict[str, Any]) -> Optional[str]:
        """Extrai transcrição do áudio usando Gemini."""
        try:
            # Usar o mesmo modelo que processa áudio
            model = genai.GenerativeModel('gemini-2.0-flash')
            
            audio_base64 = audio_data.get("base64", "")
            audio_bytes = base64.b64decode(audio_base64)
            
            # Prompt específico para transcrição
            content_parts = [
                "Transcreva este áudio em português brasileiro. Retorne apenas a transcrição, sem comentários adicionais.",
                {
                    "mime_type": "audio/mp3",
                    "data": audio_bytes
                }
            ]
            
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: model.generate_content(content_parts)
            )
            
            return response.text if response.text else None
            
        except Exception as e:
            logger.error(f"Erro ao transcrever áudio: {e}")
            return None

    async def generate_response_with_audio(
        self, 
        messages: List[Dict[str, str]], 
        audio_data: Dict[str, Any], 
        **kwargs
    ) -> Tuple[str, Dict[str, int]]:
        """
        Gera uma resposta com suporte a áudio usando Gemini.
        """
        try:
            # Preparar o áudio
            audio_base64 = audio_data.get("base64", "")
            if not audio_base64:
                return await self.generate_response(messages, **kwargs)
            
            # Decodificar o áudio base64
            audio_bytes = base64.b64decode(audio_base64)
            
            # CORREÇÃO: Extrair system instruction e manter conversa
            system_instruction = ""
            conversation_messages = []
            
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                
                if role == "system":
                    system_instruction += content + "\n"
                elif role in ["user", "assistant"]:
                    # Manter a conversa completa, convertendo assistant -> model
                    gemini_role = "model" if role == "assistant" else "user"
                    conversation_messages.append({
                        "role": gemini_role,
                        "parts": [{"text": content}]
                    })
            
            # Usar modelo com system_instruction
            model = genai.GenerativeModel(
                'gemini-2.0-flash',
                system_instruction=system_instruction.strip() if system_instruction else "Você é um assistente útil."
            )
            
            # Preparar conteúdo: última mensagem do usuário + áudio
            # Encontrar a última mensagem do usuário
            last_user_message = ""
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    last_user_message = msg.get("content", "")
                    break
            
            content_parts = [
                last_user_message,
                {
                    "mime_type": "audio/mp3", 
                    "data": audio_bytes
                }
            ]
            
            # Usar startChat para manter contexto da conversa
            # Remover a última mensagem do usuário do histórico (será enviada separadamente)
            history = conversation_messages[:-1] if conversation_messages and conversation_messages[-1]["role"] == "user" else conversation_messages
            
            # Gerar resposta
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self._generate_with_audio_sync(model, history, content_parts)
            )
            
            # Contagem de tokens (estimativa)
            token_usage = {
                "prompt_tokens": sum(len(msg.get("content", "").split()) for msg in messages) + 100,
                "completion_tokens": len(response.text.split()) if response.text else 0,
                "total_tokens": 0
            }
            token_usage["total_tokens"] = token_usage["prompt_tokens"] + token_usage["completion_tokens"]
            
            return response.text, token_usage
            
        except Exception as e:
            logger.error(f"Erro ao processar áudio com Gemini: {e}")
            return await self.generate_response(messages, **kwargs)
        
    def _generate_sync(self, messages, generation_config):
        """Método síncrono para gerar resposta com Gemini."""
        try:
            # Configurar o modelo
            model = genai.GenerativeModel(
                model_name=self.model,
                safety_settings=self.safety_settings,
                generation_config=generation_config
            )
            
            print(f"[DEBUG] _generate_sync: Model: {model.model_name} | API Key: {self.api_key[-10:]}")
            
            # CORREÇÃO: Usar o formato correto para conversas
            if len(messages) == 1:
                # Uma única mensagem
                return model.generate_content(messages[0]["parts"][0]["text"])
            
            # Para conversas, usar startChat com history
            # Separar a última mensagem do histórico
            history = messages[:-1] if len(messages) > 1 else []
            current_message = messages[-1]["parts"][0]["text"]
            
            chat = model.start_chat(history=history)
            return chat.send_message(current_message)
            
        except Exception as e:
            logger.error(f"Error in sync generation: {e}")
            print(f"[DEBUG][DEBUG] _generate_sync: Error in sync generation: {e} | API Key: {self.api_key[-10:]}") 
            # Retornar um objeto mock com texto de erro
            class MockResponse:
                def __init__(self, text):
                    self.text = text
            return MockResponse(f"Erro na geração: {str(e)}")
        
    def _generate_with_audio_sync(self, model, history, content_parts):
        """Método síncrono para gerar resposta com áudio e histórico."""
        try:
            if history:
                # Usar chat com histórico
                chat = model.start_chat(history=history)
                return chat.send_message(content_parts)
            else:
                # Primeira mensagem
                return model.generate_content(content_parts)
        except Exception as e:
            logger.error(f"Error in audio sync generation: {e}")
            class MockResponse:
                def __init__(self, text):
                    self.text = text
            return MockResponse(f"Erro na geração com áudio: {str(e)}")

    async def generate_with_functions(
        self, 
        messages: List[Dict[str, str]], 
        functions: List[Dict[str, Any]], 
        function_call: str = "auto"
    ) -> Tuple[Dict[str, Any], Dict[str, int]]:
        """
        Gera uma resposta com suporte a chamadas de função usando Gemini Function Calling.
        """
        try:
            # Converter funções para o formato do Gemini
            gemini_functions = self._convert_functions_to_gemini_format(functions)
            
            # Converter mensagens
            gemini_messages = self._convert_to_gemini_format(messages)
            
            # Configurações de geração
            generation_config = {
                "temperature": 0.7,
                "max_output_tokens": 1000,
            }
            
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                self._executor,
                self._generate_with_functions_sync,
                gemini_messages,
                gemini_functions,
                generation_config
            )
            
            # Processar resposta
            result_message = self._process_function_response(response)
            
            # Calcular tokens
            prompt_text = " ".join([msg.get("content", "") for msg in messages])
            prompt_tokens = await self.count_tokens(prompt_text)
            
            response_text = str(result_message)
            completion_tokens = await self.count_tokens(response_text)
            
            token_usage = {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens
            }
            
            return result_message, token_usage
            
        except Exception as e:
            logger.error(f"Error generating response with functions: {e}")
            error_response = {
                "role": "assistant",
                "content": f"Erro ao processar função: {str(e)}"
            }
            token_usage = {
                "prompt_tokens": 0,
                "completion_tokens": 10,
                "total_tokens": 10
            }
            return error_response, token_usage

    def _generate_with_functions_sync(self, messages, functions, generation_config):
        """Método síncrono para gerar resposta com funções."""
        try:
            model = genai.GenerativeModel(
                model_name=self.model,
                tools=functions,
                safety_settings=self.safety_settings,
                generation_config=generation_config
            )
            
            # Iniciar chat com função
            chat = model.start_chat()
            
            # Enviar mensagem
            if len(messages) == 1:
                return chat.send_message(messages[0])
            else:
                # Para múltiplas mensagens, enviar a última
                return chat.send_message(messages[-1])
                
        except Exception as e:
            logger.error(f"Error in sync function generation: {e}")
            return None

    def _convert_functions_to_gemini_format(self, functions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Converte funções do formato OpenAI para o formato Gemini."""
        gemini_functions = []
        
        for func in functions:
            # Gemini usa um formato diferente para funções
            gemini_func = {
                "name": func.get("name"),
                "description": func.get("description"),
                "parameters": func.get("parameters", {})
            }
            gemini_functions.append(gemini_func)
        
        return gemini_functions

    def _process_function_response(self, response) -> Dict[str, Any]:
        """Processa a resposta do Gemini que pode conter chamadas de função."""
        try:
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                
                # Verificar se há chamadas de função
                if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                    for part in candidate.content.parts:
                        if hasattr(part, 'function_call'):
                            # Há uma chamada de função
                            function_call = part.function_call
                            return {
                                "role": "assistant",
                                "content": None,
                                "function_call": {
                                    "name": function_call.name,
                                    "arguments": str(function_call.args)
                                }
                            }
                        elif hasattr(part, 'text'):
                            # Resposta de texto normal
                            return {
                                "role": "assistant",
                                "content": part.text
                            }
            
            # Fallback para resposta simples
            return {
                "role": "assistant",
                "content": response.text if hasattr(response, 'text') else str(response)
            }
            
        except Exception as e:
            logger.error(f"Error processing function response: {e}")
            return {
                "role": "assistant",
                "content": f"Erro ao processar resposta: {str(e)}"
            }

    async def get_embeddings(self, text: str) -> List[float]:
        """
        Obtém embeddings usando o modelo de embedding do Gemini.
        """
        try:
            # Usar modelo de embedding do Gemini
            loop = asyncio.get_event_loop()
            embedding = await loop.run_in_executor(
                self._executor,
                self._get_embedding_sync,
                text
            )
            return embedding
            
        except Exception as e:
            logger.error(f"Error getting Gemini embedding: {e}")
            # Retornar embedding aleatório como fallback
            import random
            return [random.random() for _ in range(768)]  # Gemini embeddings são 768D

    def _get_embedding_sync(self, text: str) -> List[float]:
        """Método síncrono para obter embedding."""
        try:
            # Usar o modelo de embedding do Gemini
            result = genai.embed_content(
                model="models/embedding-001",
                content=text,
                task_type="retrieval_document"
            )
            return result['embedding']
        except Exception as e:
            logger.error(f"Error in sync embedding: {e}")
            # Retornar embedding aleatório
            import random
            return [random.random() for _ in range(768)]

    def _convert_to_gemini_format(self, messages: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """
        Converte mensagens do formato OpenAI para o formato Gemini.
        Gemini usa apenas roles: 'user' e 'model' (não 'assistant').
        """
        gemini_messages = []
        system_instructions = []
        
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "system":
                # Coletar instruções do sistema separadamente
                system_instructions.append(content)
            elif role == "user":
                gemini_messages.append({
                    "role": "user",
                    "parts": [{"text": content}]
                })
            elif role == "assistant":
                # CORREÇÃO: Gemini usa 'model', não 'assistant'
                gemini_messages.append({
                    "role": "model", 
                    "parts": [{"text": content}]
                })
        
        # Se há instruções do sistema, adicionar como primeira mensagem do usuário
        if system_instructions:
            system_text = "\n\n".join(system_instructions)
            # Inserir no início
            gemini_messages.insert(0, {
                "role": "user",
                "parts": [{"text": f"Instruções do sistema: {system_text}"}]
            })
            # Adicionar resposta model de confirmação
            gemini_messages.insert(1, {
                "role": "model",
                "parts": [{"text": "Entendido. Seguirei essas instruções."}]
            })
        
        return gemini_messages

    def __del__(self):
        """Cleanup ao destruir o objeto."""
        if hasattr(self, '_executor'):
            self._executor.shutdown(wait=False)