# admin/views/tokens.py
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
import requests
from datetime import datetime, timedelta

from admin.config import Config

import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("admin.views.tokens")

tokens_bp = Blueprint('tokens', __name__, url_prefix='/tokens')

def get_api_headers():
    headers = {
        'Content-Type': 'application/json',
    }
    
    # Add token if user is authenticated
    if hasattr(current_user, 'token') and current_user.token:
        headers['Authorization'] = f'Bearer {current_user.token}'
    
    # Add tenant ID if available
    if hasattr(current_user, 'tenant_id') and current_user.tenant_id:
        headers['X-Tenant-ID'] = str(current_user.tenant_id)
    
    return headers

@tokens_bp.route('/')
@login_required
def index():
    """Dashboard principal de uso de tokens."""
    # Verificar se o usuário é admin
    is_admin = current_user.is_superuser
    
    # Obter dados do dashboard de tokens
    try:
        response = requests.get(
            f"{Config.API_URL}/dashboard/token-usage",
            headers=get_api_headers(),
            timeout=10
        )
        
        if response.status_code == 200:
            token_data = response.json()
        else:
            flash(f"Erro ao obter dados de uso de tokens: {response.status_code}", "danger")
            token_data = {
                "daily_usage": [],
                "monthly_usage": [],
                "agent_usage": [],
                "model_usage": [],
                "limits": [],
                "alerts": []
            }
    except requests.exceptions.RequestException as e:
        flash(f"Erro ao conectar à API: {e}", "danger")
        token_data = {
            "daily_usage": [],
            "monthly_usage": [],
            "agent_usage": [],
            "model_usage": [],
            "limits": [],
            "alerts": []
        }
    
    # Processar dados para gráficos
    daily_labels = []
    daily_values = []
    
    for day in token_data.get("daily_usage", []):
        daily_labels.append(day.get("period_value"))
        daily_values.append(day.get("total_tokens", 0))
    
    monthly_labels = []
    monthly_values = []
    
    for month in token_data.get("monthly_usage", []):
        monthly_labels.append(month.get("period_value"))
        monthly_values.append(month.get("total_tokens", 0))
    
    # Dados para gráfico de pizza de uso por agente
    agent_labels = []
    agent_values = []
    agent_colors = []
    
    # Gerar cores aleatórias
    import random
    
    for idx, agent in enumerate(token_data.get("agent_usage", [])):
        agent_labels.append(agent.get("agent_name", f"Agente {idx+1}"))
        agent_values.append(agent.get("total_tokens", 0))
        
        # Gerar cor HSL aleatória
        hue = random.randint(0, 360)
        agent_colors.append(f"hsl({hue}, 70%, 60%)")
    
    return render_template(
        'tokens/index.html',
        token_data=token_data,
        daily_labels=daily_labels,
        daily_values=daily_values,
        monthly_labels=monthly_labels,
        monthly_values=monthly_values,
        agent_labels=agent_labels,
        agent_values=agent_values,
        agent_colors=agent_colors,
        is_admin=is_admin
    )

@tokens_bp.route('/limits')
@login_required
def limits():
   """Página de gerenciamento de limites de tokens."""
   # Obter limites atuais
   try:
       response = requests.get(
           f"{Config.API_URL}/token-limits/limits",
           headers=get_api_headers(),
           timeout=5
       )
       
       if response.status_code == 200:
           limits = response.json()
       else:
           flash(f"Erro ao obter limites de tokens: {response.status_code}", "danger")
           limits = []
   except requests.exceptions.RequestException as e:
       flash(f"Erro ao conectar à API: {e}", "danger")
       limits = []
   
   # Obter lista de tenants (somente para admin)
   tenants = []
   if current_user.is_superuser:
       try:
           response = requests.get(
               f"{Config.API_URL}/tenants/",
               headers=get_api_headers(),
               timeout=5
           )
           
           if response.status_code == 200:
               tenants = response.json()
       except requests.exceptions.RequestException:
           pass
   
   # Obter lista de agentes
   agents = []
   try:
       tenant_id = current_user.tenant_id if current_user.tenant_id else None
       params = {"tenant_id": tenant_id} if tenant_id else {}
       
       response = requests.get(
           f"{Config.API_URL}/agents/",
           headers=get_api_headers(),
           params=params,
           timeout=5
       )
       
       if response.status_code == 200:
           agents = response.json()
   except requests.exceptions.RequestException:
       pass
   
   return render_template(
       'tokens/limits.html',
       limits=limits,
       tenants=tenants,
       agents=agents,
       is_admin=current_user.is_superuser
   )

@tokens_bp.route('/limits/create', methods=['POST'])
@login_required
def create_limit():
   """Cria um novo limite de uso de tokens."""
   # Obter dados do formulário
   tenant_id = request.form.get('tenant_id', type=int) or current_user.tenant_id
   agent_id = request.form.get('agent_id')
   monthly_limit = request.form.get('monthly_limit', type=int)
   daily_limit = request.form.get('daily_limit', type=int)
   warning_threshold = request.form.get('warning_threshold', type=float, default=0.8)
   notify_email = request.form.get('notify_email')
   notify_webhook_url = request.form.get('notify_webhook_url')
   
   # Validar dados
   if not monthly_limit:
       flash("Limite mensal é obrigatório", "danger")
       return redirect(url_for('tokens.limits'))
   
   # Preparar payload
   limit_data = {
       "tenant_id": tenant_id,
       "agent_id": agent_id if agent_id else None,
       "monthly_limit": monthly_limit,
       "daily_limit": daily_limit,
       "warning_threshold": warning_threshold,
       "notify_email": notify_email,
       "notify_webhook_url": notify_webhook_url,
       "is_active": True
   }
   
   # Enviar para API
   try:
       response = requests.post(
           f"{Config.API_URL}/token-limits/limits",
           headers=get_api_headers(),
           json=limit_data,
           timeout=10
       )
       
       if response.status_code == 200:
           flash("Limite de tokens criado com sucesso!", "success")
       else:
           error_detail = "Erro desconhecido"
           try:
               error_data = response.json()
               error_detail = error_data.get('detail', str(response.status_code))
           except:
               error_detail = f"Erro {response.status_code}"
           
           flash(f"Erro ao criar limite de tokens: {error_detail}", "danger")
   except requests.exceptions.RequestException as e:
       flash(f"Erro ao conectar à API: {e}", "danger")
   
   return redirect(url_for('tokens.limits'))

@tokens_bp.route('/limits/<int:limit_id>/edit', methods=['POST'])
@login_required
def update_limit(limit_id):
   """Atualiza um limite de uso de tokens existente."""
   # Obter dados do formulário
   monthly_limit = request.form.get('monthly_limit', type=int)
   daily_limit = request.form.get('daily_limit', type=int)
   warning_threshold = request.form.get('warning_threshold', type=float)
   notify_email = request.form.get('notify_email')
   notify_webhook_url = request.form.get('notify_webhook_url')
   is_active = 'is_active' in request.form
   
   # Preparar payload (somente campos fornecidos)
   limit_data = {}
   
   if monthly_limit is not None:
       limit_data["monthly_limit"] = monthly_limit
   
   if daily_limit is not None:
       limit_data["daily_limit"] = daily_limit
   
   if warning_threshold is not None:
       limit_data["warning_threshold"] = warning_threshold
   
   limit_data["notify_email"] = notify_email
   limit_data["notify_webhook_url"] = notify_webhook_url
   limit_data["is_active"] = is_active
   
   # Enviar para API
   try:
       response = requests.put(
           f"{Config.API_URL}/token-limits/limits/{limit_id}",
           headers=get_api_headers(),
           json=limit_data,
           timeout=10
       )
       
       if response.status_code == 200:
           flash("Limite de tokens atualizado com sucesso!", "success")
       else:
           error_detail = "Erro desconhecido"
           try:
               error_data = response.json()
               error_detail = error_data.get('detail', str(response.status_code))
           except:
               error_detail = f"Erro {response.status_code}"
           
           flash(f"Erro ao atualizar limite de tokens: {error_detail}", "danger")
   except requests.exceptions.RequestException as e:
       flash(f"Erro ao conectar à API: {e}", "danger")
   
   return redirect(url_for('tokens.limits'))

@tokens_bp.route('/limits/<int:limit_id>/delete', methods=['POST'])
@login_required
def delete_limit(limit_id):
   """Remove um limite de uso de tokens."""
   try:
       response = requests.delete(
           f"{Config.API_URL}/token-limits/limits/{limit_id}",
           headers=get_api_headers(),
           timeout=5
       )
       
       if response.status_code == 200:
           flash("Limite de tokens removido com sucesso!", "success")
       else:
           error_detail = "Erro desconhecido"
           try:
               error_data = response.json()
               error_detail = error_data.get('detail', str(response.status_code))
           except:
               error_detail = f"Erro {response.status_code}"
           
           flash(f"Erro ao remover limite de tokens: {error_detail}", "danger")
   except requests.exceptions.RequestException as e:
       flash(f"Erro ao conectar à API: {e}", "danger")
   
   return redirect(url_for('tokens.limits'))

@tokens_bp.route('/alerts')
@login_required
def alerts():
   """Página de alertas de uso de tokens."""
   try:
       response = requests.get(
           f"{Config.API_URL}/token-limits/alerts",
           headers=get_api_headers(),
           timeout=5
       )
       
       if response.status_code == 200:
           alerts = response.json()
       else:
           flash(f"Erro ao obter alertas de tokens: {response.status_code}", "danger")
           alerts = []
   except requests.exceptions.RequestException as e:
       flash(f"Erro ao conectar à API: {e}", "danger")
       alerts = []
   
   return render_template(
       'tokens/alerts.html',
       alerts=alerts,
       is_admin=current_user.is_superuser
   )

@tokens_bp.route('/usage')
@login_required
def usage():
   """Página de visualização detalhada de uso de tokens."""
   # Parâmetros de filtragem
   tenant_id = request.args.get('tenant_id', type=int) or (current_user.tenant_id if not current_user.is_superuser else None)
   agent_id = request.args.get('agent_id')
   period = request.args.get('period', 'monthly')
   
   # Parâmetros de URL
   params = {}
   if tenant_id:
       params['tenant_id'] = tenant_id
   if agent_id:
       params['agent_id'] = agent_id
   if period:
       params['period'] = period
   
   # Obter uso de tokens
   try:
       response = requests.get(
           f"{Config.API_URL}/token-limits/usage",
           headers=get_api_headers(),
           params=params,
           timeout=10
       )
       
       if response.status_code == 200:
           usage_data = response.json()
       else:
           flash(f"Erro ao obter dados de uso de tokens: {response.status_code}", "danger")
           usage_data = []
   except requests.exceptions.RequestException as e:
       flash(f"Erro ao conectar à API: {e}", "danger")
       usage_data = []
   
   # Obter lista de tenants (somente para admin)
   tenants = []
   if current_user.is_superuser:
       try:
           response = requests.get(
               f"{Config.API_URL}/tenants/",
               headers=get_api_headers(),
               timeout=5
           )
           
           if response.status_code == 200:
               tenants = response.json()
       except requests.exceptions.RequestException:
           pass
   
   # Obter lista de agentes
   agents = []
   try:
       agent_params = {"tenant_id": tenant_id} if tenant_id else {}
       
       response = requests.get(
           f"{Config.API_URL}/agents/",
           headers=get_api_headers(),
           params=agent_params,
           timeout=5
       )
       
       if response.status_code == 200:
           agents = response.json()
   except requests.exceptions.RequestException:
       pass
   
   # Processar dados para gráficos
   labels = []
   total_values = []
   prompt_values = []
   completion_values = []
   cost_values = []
   
   for item in usage_data:
       labels.append(item.get("period_value"))
       total_values.append(item.get("total_tokens", 0))
       prompt_values.append(item.get("prompt_tokens", 0))
       completion_values.append(item.get("completion_tokens", 0))
       cost_values.append(item.get("total_cost_usd", 0))
   
   # Calcular somatórios
   total_tokens = sum(total_values)
   total_cost = sum(cost_values)
   limit_value = usage_data[0].get("limit_value") if usage_data else None
   
   return render_template(
       'tokens/usage.html',
       usage_data=usage_data,
       tenants=tenants,
       agents=agents,
       labels=labels,
       total_values=total_values,
       prompt_values=prompt_values,
       completion_values=completion_values,
       cost_values=cost_values,
       total_tokens=total_tokens,
       total_cost=total_cost,
       limit_value=limit_value,
       current_tenant_id=tenant_id,
       current_agent_id=agent_id,
       current_period=period,
       is_admin=current_user.is_superuser
   )