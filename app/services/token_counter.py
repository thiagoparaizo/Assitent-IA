# app/services/token_counter.py
import asyncio
from datetime import datetime, timedelta
import uuid
from typing import Dict, List, Optional, Tuple, Any
import httpx
from sqlalchemy import func, and_, extract
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.db.models.token_usage import TokenUsageLimit, TokenUsageLog, TokenUsageAlert
from app.db.models.agent import Agent
from app.db.models.tenant import Tenant
from app.db.models.llm_model import LLMModel
from app.services.notification import NotificationService
from app.core.config import settings

logger = logging.getLogger(__name__)

class TokenCounterService:
    """Serviço para contagem, registro e monitoramento de uso de tokens LLM."""
    
    def __init__(self, db_session, notification_service=None):
        self.db = db_session
        self.notification_service = notification_service or NotificationService(db_session)
    
    async def count_tokens(self, text: str, model_name: str = None) -> int:
        """Conta tokens em um texto usando um modelo específico."""
        try:
            # Aqui podemos usar diferentes métodos dependendo do modelo
            # Para OpenAI, podemos usar tiktoken
            import tiktoken
            
            # Determinar o codificador apropriado
            encoder_name = "cl100k_base"  # Padrão para modelos mais recentes
            if model_name:
                if "gpt-3.5" in model_name:
                    encoder_name = "cl100k_base"
                elif "gpt-4" in model_name:
                    encoder_name = "cl100k_base"
                # adicionar outros modelos conforme necessário
            
            # Obter o codificador e contar tokens
            encoder = tiktoken.get_encoding(encoder_name)
            return len(encoder.encode(text))
        
        except ImportError:
            # Fallback para estimativa básica (menos precisa)
            # Aproximadamente 4 caracteres por token
            return len(text) // 4
    
    async def log_token_usage(
        self, 
        tenant_id: int, 
        agent_id: str, 
        model_id: int,
        prompt_tokens: int,
        completion_tokens: int,
        conversation_id: str = None
    ) -> TokenUsageLog:
        """Registra o uso de tokens em uma chamada LLM."""
        # Calcular total de tokens
        total_tokens = prompt_tokens + completion_tokens
        
        # Obter informações do modelo para estimar custo
        model_query = self.db.query(LLMModel).filter(LLMModel.id == model_id)
        model = model_query.first()
        
        # Calcular custo estimado
        cost_per_1k = model.cost_per_1k_tokens if model else 0.0
        estimated_cost = (total_tokens / 1000) * cost_per_1k
        
        # Criar o registro de uso
        usage_log = TokenUsageLog(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            conversation_id=conversation_id,
            model_id=model_id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=estimated_cost,
            timestamp=datetime.utcnow()
        )
        
        self.db.add(usage_log)
        self.db.commit()
        self.db.refresh(usage_log)
        
        # Verificar limites após registrar o uso
        asyncio.create_task(self.check_token_limits(tenant_id, agent_id))
        
        return usage_log
    
    async def check_token_limits(self, tenant_id: int, agent_id: str = None):
        """Verifica se os limites de uso de tokens foram atingidos."""
        # Obter a data atual
        now = datetime.utcnow()
        current_month = now.month
        current_year = now.year
        current_day = now.day
        
        # 1. Verificar limites mensais
        await self._check_monthly_limits(tenant_id, agent_id, current_year, current_month)
        
        # 2. Verificar limites diários (se configurados)
        await self._check_daily_limits(tenant_id, agent_id, current_year, current_month, current_day)
        
    async def _check_monthly_limits(self, tenant_id: int, agent_id: str, year: int, month: int):
        """Verifica limites mensais de uso de tokens."""
        # Construir consulta para obter total de tokens usados no mês
        query = self.db.query(func.sum(TokenUsageLog.total_tokens).label("total_tokens"))
        query = query.filter(
            TokenUsageLog.tenant_id == tenant_id,
            extract('year', TokenUsageLog.timestamp) == year,
            extract('month', TokenUsageLog.timestamp) == month
        )
        
        # Se agent_id for especificado, filtrar por agente
        if agent_id:
            query = query.filter(TokenUsageLog.agent_id == agent_id)
            
            # Obter limites específicos do agente
            limits = self.db.query(TokenUsageLimit).filter(
                TokenUsageLimit.agent_id == agent_id,
                TokenUsageLimit.is_active == True
            ).all()
        else:
            # Obter limites do tenant
            limits = self.db.query(TokenUsageLimit).filter(
                TokenUsageLimit.tenant_id == tenant_id,
                TokenUsageLimit.agent_id == None,
                TokenUsageLimit.is_active == True
            ).all()
        
        # Obter total de tokens usados
        result = query.first()
        total_used = result.total_tokens if result and result.total_tokens else 0
        
        # Verificar cada limite configurado
        for limit in limits:
            if limit.monthly_limit and total_used > 0:
                usage_percentage = total_used / limit.monthly_limit
                
                # Verificar se o limite de alerta foi atingido
                if usage_percentage >= limit.warning_threshold:
                    await self._create_or_update_alert(
                        tenant_id=tenant_id,
                        agent_id=agent_id,
                        limit_type="monthly",
                        threshold_value=limit.warning_threshold,
                        current_usage=total_used,
                        max_limit=limit.monthly_limit,
                        notification_channel="email" if limit.notify_email else "webhook",
                        notification_target=limit.notify_email or limit.notify_webhook_url
                    )
    
    async def _check_daily_limits(self, tenant_id: int, agent_id: str, year: int, month: int, day: int):
        """Verifica limites diários de uso de tokens."""
        # Semelhante ao _check_monthly_limits, mas filtrando por dia
        query = self.db.query(func.sum(TokenUsageLog.total_tokens).label("total_tokens"))
        query = query.filter(
            TokenUsageLog.tenant_id == tenant_id,
            extract('year', TokenUsageLog.timestamp) == year,
            extract('month', TokenUsageLog.timestamp) == month,
            extract('day', TokenUsageLog.timestamp) == day
        )
        
        if agent_id:
            query = query.filter(TokenUsageLog.agent_id == agent_id)
            limits = self.db.query(TokenUsageLimit).filter(
                TokenUsageLimit.agent_id == agent_id,
                TokenUsageLimit.is_active == True,
                TokenUsageLimit.daily_limit != None  # Somente limites diários configurados
            ).all()
        else:
            limits = self.db.query(TokenUsageLimit).filter(
                TokenUsageLimit.tenant_id == tenant_id,
                TokenUsageLimit.agent_id == None,
                TokenUsageLimit.is_active == True,
                TokenUsageLimit.daily_limit != None  # Somente limites diários configurados
            ).all()
        
        result = query.first()
        total_used = result.total_tokens if result and result.total_tokens else 0
        
        for limit in limits:
            if limit.daily_limit and total_used > 0:
                usage_percentage = total_used / limit.daily_limit
                
                if usage_percentage >= limit.warning_threshold:
                    await self._create_or_update_alert(
                        tenant_id=tenant_id,
                        agent_id=agent_id,
                        limit_type="daily",
                        threshold_value=limit.warning_threshold,
                        current_usage=total_used,
                        max_limit=limit.daily_limit,
                        notification_channel="email" if limit.notify_email else "webhook",
                        notification_target=limit.notify_email or limit.notify_webhook_url
                    )
    
    async def _create_or_update_alert(
        self,
        tenant_id: int,
        agent_id: str = None,
        limit_type: str = "monthly",
        threshold_value: float = 0.8,
        current_usage: int = 0,
        max_limit: int = 0,
        notification_channel: str = None,
        notification_target: str = None
    ):
        """Cria ou atualiza um alerta de uso de tokens."""
        # Verificar se já existe um alerta recente (últimas 24 horas)
        yesterday = datetime.utcnow() - timedelta(days=1)
        
        query = self.db.query(TokenUsageAlert).filter(
            TokenUsageAlert.tenant_id == tenant_id,
            TokenUsageAlert.limit_type == limit_type,
            TokenUsageAlert.created_at >= yesterday
        )
        
        if agent_id:
            query = query.filter(TokenUsageAlert.agent_id == agent_id)
        else:
            query = query.filter(TokenUsageAlert.agent_id == None)
        
        existing_alert = query.order_by(TokenUsageAlert.created_at.desc()).first()
        
        # Se já existir um alerta recente, atualizar apenas se o uso aumentou significativamente
        if existing_alert:
            # Só cria um novo alerta se o uso aumentou pelo menos 5%
            usage_increase = (current_usage - existing_alert.current_usage) / max_limit
            
            if usage_increase < 0.05:
                return existing_alert
        
        # Criar novo alerta
        alert = TokenUsageAlert(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            limit_type=limit_type,
            threshold_value=threshold_value,
            current_usage=current_usage,
            max_limit=max_limit,
            notification_channel=notification_channel,
            notification_target=notification_target,
            notification_sent=False,
            created_at=datetime.utcnow()
        )
        
        self.db.add(alert)
        self.db.commit()
        self.db.refresh(alert)
        
        # Enviar notificação
        if notification_channel and notification_target:
            success = await self.notification_service.send_token_usage_alert(
                alert, 
                channel=notification_channel, 
                target=notification_target
            )
            
            if success:
                alert.notification_sent = True
                self.db.commit()
        
        return alert
    
    async def get_token_usage_summary(
        self,
        tenant_id: Optional[int] = None,
        agent_id: Optional[str] = None,
        period: str = "monthly",  # "daily", "monthly", "yearly"
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Obtém um resumo do uso de tokens para um tenant ou agente específico.
        """
        # Determinar datas de início e fim se não forem fornecidas
        if not end_date:
            end_date = datetime.utcnow()
        
        if not start_date:
            if period == "daily":
                start_date = end_date - timedelta(days=30)  # Últimos 30 dias
            elif period == "monthly":
                start_date = end_date - timedelta(days=365)  # Últimos 12 meses
            else:  # yearly
                start_date = end_date - timedelta(days=365 * 3)  # Últimos 3 anos
        
        # Configurar agrupamento com base no período
        if period == "daily":
            # Agrupar por dia
            date_group = func.date_trunc('day', TokenUsageLog.timestamp)
            date_format = "%Y-%m-%d"
        elif period == "monthly":
            # Agrupar por mês
            date_group = func.date_trunc('month', TokenUsageLog.timestamp)
            date_format = "%Y-%m"
        else:  # yearly
            # Agrupar por ano
            date_group = func.date_trunc('year', TokenUsageLog.timestamp)
            date_format = "%Y"
        
        # Construir consulta base
        query = self.db.query(
            date_group.label("period_date"),
            func.sum(TokenUsageLog.prompt_tokens).label("prompt_tokens"),
            func.sum(TokenUsageLog.completion_tokens).label("completion_tokens"),
            func.sum(TokenUsageLog.total_tokens).label("total_tokens"),
            func.sum(TokenUsageLog.estimated_cost_usd).label("total_cost")
        ).filter(
            TokenUsageLog.timestamp.between(start_date, end_date)
        )
        
        # Filtrar por tenant e/ou agente
        if tenant_id:
            query = query.filter(TokenUsageLog.tenant_id == tenant_id)
        
        if agent_id:
            query = query.filter(TokenUsageLog.agent_id == agent_id)
        
        # Agrupar e ordenar
        query = query.group_by(date_group).order_by(date_group)
        
        # Executar consulta
        results = query.all()
        
        # Obter limite relevante se aplicável
        limit_value = None
        if tenant_id or agent_id:
            limit_query = self.db.query(TokenUsageLimit)
            
            if tenant_id and not agent_id:
                limit_query = limit_query.filter(
                    TokenUsageLimit.tenant_id == tenant_id,
                    TokenUsageLimit.agent_id == None
                )
            elif agent_id:
                limit_query = limit_query.filter(TokenUsageLimit.agent_id == agent_id)
            
            limit = limit_query.first()
            
            if limit:
                if period == "daily":
                    limit_value = limit.daily_limit
                else:
                    limit_value = limit.monthly_limit
        
        # Formatar resultados
        summaries = []
        for result in results:
            # Formatar data conforme o período
            period_value = result.period_date.strftime(date_format)
            
            # Calcular percentual do limite se aplicável
            percentage = None
            if limit_value and result.total_tokens:
                percentage = result.total_tokens / limit_value
            
            summary = {
                "tenant_id": tenant_id,
                "agent_id": agent_id,
                "period": period,
                "period_value": period_value,
                "total_tokens": result.total_tokens,
                "prompt_tokens": result.prompt_tokens,
                "completion_tokens": result.completion_tokens,
                "total_cost_usd": result.total_cost,
                "percentage_of_limit": percentage,
                "limit_value": limit_value
            }
            
            summaries.append(summary)
        
        return summaries