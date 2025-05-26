# Criar arquivo: app/utils/audio_helpers.py

import logging
from typing import Dict, Any, Optional
from app.services.llm.gemini_service import GeminiService

logger = logging.getLogger(__name__)

def llm_supports_audio(llm_service) -> bool:
    """
    Verifica se o serviço LLM suporta processamento de áudio.
    
    Args:
        llm_service: Instância do serviço LLM
        
    Returns:
        bool: True se suporta áudio, False caso contrário
    """
    # Verificar se o serviço tem o método supports_audio
    if hasattr(llm_service, 'supports_audio'):
        return llm_service.supports_audio()
    
    # Fallback: verificar por tipo
    return isinstance(llm_service, GeminiService)

def extract_audio_info(event_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Extrai informações de áudio de um evento de webhook.
    
    Args:
        event_data: Dados do evento recebido
        
    Returns:
        Dict com informações do áudio ou None se não houver áudio
    """
    audio_data = event_data.get("audio_data")
    
    if not audio_data:
        return None
    
    # Verificar se tem os campos essenciais
    if not audio_data.get("base64") or not audio_data.get("format"):
        logger.warning("Audio data incomplete, missing base64 or format")
        return None
    
    return {
        "base64": audio_data.get("base64"),
        "format": audio_data.get("format", "mp3"),
        "message_id": audio_data.get("message_id"),
        "size_estimate": len(audio_data.get("base64", "")) * 3 // 4  # Estimativa do tamanho em bytes
    }

def validate_audio_data(audio_data: Dict[str, Any]) -> bool:
    """
    Valida se os dados de áudio estão no formato correto.
    
    Args:
        audio_data: Dados do áudio para validar
        
    Returns:
        bool: True se válido, False caso contrário
    """
    required_fields = ["base64", "format"]
    
    for field in required_fields:
        if not audio_data.get(field):
            logger.error(f"Audio data missing required field: {field}")
            return False
    
    # Verificar se o base64 não está vazio
    if len(audio_data["base64"]) < 100:  # Muito pequeno para ser um áudio válido
        logger.error("Audio base64 data too small to be valid")
        return False
    
    # Verificar formato suportado
    supported_formats = ["mp3", "ogg", "wav"]
    if audio_data["format"].lower() not in supported_formats:
        logger.error(f"Unsupported audio format: {audio_data['format']}")
        return False
    
    return True

def get_audio_not_supported_response(agent_name: Optional[str] = None) -> str:
    """
    Retorna uma mensagem padrão quando áudio não é suportado.
    
    Args:
        agent_name: Nome do agente (opcional)
        
    Returns:
        str: Mensagem de resposta
    """
    base_message = "Desculpe, não estou conseguindo processar áudios nesse momento. Poderia escrever por favor?"
    
    # Adicionar nome do agente
    # if agent_name:
    #     return f"Olá! Sou a {agent_name}. {base_message}"
    
    return base_message

def get_audio_error_response(agent_name: Optional[str] = None) -> str:
    """
    Retorna uma mensagem padrão quando áudio não é processado com sucesso.
    
    Args:
        agent_name: Nome do agente (opcional)
        
    Returns:
        str: Mensagem de resposta
    """
    base_message = "Desculpe, não estou conseguindo processar áudios nesse momento. Poderia escrever por favor?"
    
    # Adicionar nome do agente
    # if agent_name:
    #     return f"Olá! Sou a {agent_name}. {base_message}"
    
    return base_message

def get_error_response_generic(agent_name: Optional[str] = None) -> str:
    """
    Retorna uma mensagem padrão quando ocorrer um erro geral.
    
    Args:
        agent_name: Nome do agente (opcional)
        
    Returns:
        str: Mensagem de resposta
    """
    base_message = "Desculpe, não estou conseguindo responder nesse momento. Você poderia tentar mais tarde? Enquando isso, vou encanhar seu contato para alguem que vai entrar em contato."
    
    # Adicionar nome do agente
    # if agent_name:
    #     return f"Olá! Sou a {agent_name}. {base_message}"
    
    return base_message

def log_audio_processing(
    device_id: int, 
    chat_jid: str, 
    audio_size: int, 
    llm_type: str, 
    success: bool = True, 
    error: Optional[str] = None
):
    """
    Registra informações sobre o processamento de áudio.
    
    Args:
        device_id: ID do dispositivo
        chat_jid: JID do chat
        audio_size: Tamanho estimado do áudio
        llm_type: Tipo do LLM usado
        success: Se o processamento foi bem-sucedido
        error: Mensagem de erro (se houver)
    """
    if success:
        logger.info(
            f"Audio processed successfully - Device: {device_id}, "
            f"Chat: {chat_jid}, Size: {audio_size} bytes, LLM: {llm_type}"
        )
    else:
        logger.error(
            f"Audio processing failed - Device: {device_id}, "
            f"Chat: {chat_jid}, LLM: {llm_type}, Error: {error}"
        )
