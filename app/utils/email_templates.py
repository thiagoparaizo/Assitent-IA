# app/templates/email_templates.py
"""
Templates específicos para diferentes tipos de notificação
"""

from typing import Dict, Any
from enum import Enum

class EmailTemplates:
    """Templates pré-definidos para diferentes cenários"""
    
    @staticmethod
    def get_whatsapp_reauth_template() -> Dict[str, Any]:
        """Template para reautenticação do WhatsApp"""
        return {
            "title": "Reautenticação Necessária",
            "subtitle": "WhatsApp Service - Ação Requerida",
            "message": """
            <p>Seu dispositivo WhatsApp precisa ser reautenticado para continuar funcionando.</p>
            <p>Este é um procedimento de segurança normal que acontece periodicamente.</p>
            """,
            "suggested_action": """
            Para reativar o dispositivo:
            1. Acesse o painel de controle
            2. Vá para a seção WhatsApp
            3. Clique em "Reconectar" no dispositivo
            4. Use o WhatsApp no seu celular para escanear o novo QR Code
            
            Se precisar de ajuda, entre em contato conosco.
            """,
            "level": "warning",
            "footer_text": "WhatsApp Service - Reautenticação Automática"
        }
    
    @staticmethod 
    def get_whatsapp_critical_update_template() -> Dict[str, Any]:
        """Template para atualizações críticas"""
        return {
            "title": "Atualização Crítica Necessária",
            "subtitle": "WhatsApp Service - URGENTE",
            "message": """
            <p><strong>⚠️ ATENÇÃO:</strong> Foi detectado que seu dispositivo WhatsApp está usando uma versão desatualizada.</p>
            <p>Sem a atualização, o dispositivo pode parar de funcionar a qualquer momento.</p>
            """,
            "suggested_action": """
            AÇÃO IMEDIATA NECESSÁRIA:
            1. Atualizar biblioteca whatsmeow para a versão mais recente
            2. Recompilar e reiniciar o serviço WhatsApp
            3. Reconectar todos os dispositivos afetados
            
            ⚠️⚠️ Sem essa atualização, TODOS os dispositivos podem parar de funcionar. ⚠️⚠️
            """,
            "level": "critical",
            "footer_text": "WhatsApp Service - Alerta de Atualização Crítica"
        }
    
    @staticmethod
    def get_webhook_failure_template() -> Dict[str, Any]:
        """Template para falhas de webhook"""
        return {
            "title": "Falha de Webhook Detectada",
            "subtitle": "Sistema de Notificações",
            "message": """
            <p>Foi detectada uma falha recorrente no webhook configurado.</p>
            <p>Isso pode impactar a entrega de notificações importantes.</p>
            """,
            "suggested_action": """
            Verificações necessárias:
            1. URL do webhook está acessível?
            2. Servidor de destino está respondendo?
            3. Configuração de autenticação está correta?
            
            Considere desabilitar o webhook temporariamente se o problema persistir.
            """,
            "level": "error",
            "footer_text": "Sistema de Monitoramento de Webhooks"
        }
    
    @staticmethod
    def get_connection_error_template() -> Dict[str, Any]:
        """Template para erros de conexão"""
        return {
            "title": "Problema de Conexão Detectado",
            "subtitle": "WhatsApp Service - Monitoramento",
            "message": """
            <p>❌ Problema de conexão detectado com seu dispositivo WhatsApp.</p>
            <p>Estamos tentando reconectar automaticamente.</p>
            """,
            "suggested_action": """
            O que estamos fazendo:
            • Tentando reconectar automaticamente
            • Monitorando a situação
            
            O que você pode fazer:
            • Verificar se seu dispositivo está conectado à internet
            • Se o problema persistir, pode ser necessário reautenticar o dispositivo
            
            Entraremos em contato se precisarmos de ações adicionais.
            """,
            "level": "warning",
            "footer_text": "WhatsApp Service - Monitoramento de Conexão"
        }
    
    @staticmethod
    def get_token_limit_critical_template() -> Dict[str, Any]:
        """Template para limite crítico de tokens"""
        return {
            "title": "Limite de Tokens Crítico",
            "subtitle": "Sistema de Monitoramento LLM",
            "message": """
            <p><strong>🚨 LIMITE QUASE ATINGIDO!</strong></p>
            <p>O uso de tokens LLM atingiu um nível crítico (95%+ do limite).</p>
            <p>Ação imediata necessária para evitar interrupções no serviço.</p>
            """,
            "suggested_action": """
            Ações recomendadas IMEDIATAS:
            1. Aumentar o limite de tokens temporariamente
            2. Revisar configurações dos agentes para otimizar uso
            3. Verificar se há loops ou uso excessivo desnecessário
            4. Considerar implementar cache de respostas
            
            ⚠️ Sem ação, o serviço pode ser interrompido automaticamente.
            """,
            "level": "critical",
            "footer_text": "Sistema de Monitoramento de Tokens LLM"
        }
    
    @staticmethod
    def get_system_health_degraded_template() -> Dict[str, Any]:
        """Template para degradação de saúde do sistema"""
        return {
            "title": "Saúde do Sistema Degradada",
            "subtitle": "Monitoramento de Infraestrutura",
            "message": """
            <p>⚠️ O sistema apresenta sinais de degradação de performance.</p>
            <p>Alguns serviços podem estar operando com latência elevada.</p>
            """,
            "suggested_action": """
            Verificações recomendadas:
            1. Monitorar uso de recursos (CPU, memória, disco)
            2. Verificar logs de erro recentes
            3. Revisar conexões de banco de dados
            4. Considerar scaling horizontal se necessário
            
            Sistema permanece operacional, mas requer atenção.
            """,
            "level": "warning",
            "footer_text": "Sistema de Monitoramento de Infraestrutura"
        }



