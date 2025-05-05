# admin/views/dashboard.py
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
import requests
from datetime import datetime, timedelta
import random

from admin.config import Config

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

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

@dashboard_bp.route('/')
@login_required
def index():
    # Estatísticas
    stats = {
        'active_agents': 0,
        'conversations_today': 0,
        'knowledge_count': 0,
        'whatsapp_devices': 0
    }
    
    # # Dados para gráficos (simulados para exemplo)
    # chart_data = {
    #     'dates': [(datetime.now() - timedelta(days=i)).strftime('%d/%m') for i in range(7, 0, -1)],
    #     'conversations': [random.randint(5, 20) for _ in range(7)],
    #     'messages': [random.randint(30, 100) for _ in range(7)],
    #     'agent_names': ['Agente Geral', 'Especialista Ortho', 'Especialista Limpeza', 'Outros'],
    #     'agent_counts': [random.randint(10, 30) for _ in range(4)],
    #     'agent_colors': ['#4e73df', '#1cc88a', '#36b9cc', '#f6c23e'],
    #     'agent_hover_colors': ['#2e59d9', '#17a673', '#2c9faf', '#dda20a'],
    # }
    # Dados padrão para gráficos
    dates = [(datetime.now() - timedelta(days=i)).strftime('%d/%m') for i in range(6, -1, -1)]
    chart_data = {
        'dates': dates,
        'conversations': [0] * 7,
        'messages': [0] * 7,
        'agent_names': ['Agente Geral'],
        'agent_counts': [1],
        'agent_colors': ['#4e73df'],
        'agent_hover_colors': ['#2e59d9'],
    }
    
    # Conversas recentes (simuladas para exemplo)
    recent_conversations = []
    for i in range(5):
        recent_conversations.append({
            'id': f"conv-{i}-{''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=24))}",
            'user_id': f"+55119{random.randint(1000000, 9999999)}",
            'agent_name': random.choice(chart_data['agent_names']),
            'started_at': datetime.now() - timedelta(hours=random.randint(1, 24)),
            'message_count': random.randint(5, 20),
            'is_active': random.choice([True, False])
        })
    
    # Principais agentes (simulados para exemplo)
    top_agents = []
    
    
    # Tentar obter dados reais via API
    try:
        # Obter estatísticas básicas
        response = requests.get(
            f"{Config.API_URL}/dashboard/stats",
            headers=get_api_headers()
        )
        if response.status_code == 200:
            stats = response.json()
        
        # Obter dados de gráficos
        response = requests.get(
            f"{Config.API_URL}/dashboard/charts",
            headers=get_api_headers()
        )
        if response.status_code == 200:
            chart_data = response.json()
        
        # Obter conversas recentes
        response = requests.get(
            f"{Config.API_URL}/conversations/recent",
            headers=get_api_headers()
        )
        if response.status_code == 200:
            recent_conversations = response.json()
            
        # Obter agentes principais
        response = requests.get(
            f"{Config.API_URL}/agents/",
            headers=get_api_headers(),
            timeout=5
        )
        if response.status_code == 200:
            agents = response.json()
            
            # Extrair informações para o gráfico
            for i, agent in enumerate(agents[:5]):
                color = chart_data['agent_colors'][i % len(chart_data['agent_colors'])] if i < len(chart_data['agent_colors']) else f"#{''.join([f'{x:02x}' for x in [100 + i * 30, 100 + i * 20, 200 - i * 25]])}"
                
                top_agents.append({
                    'name': agent['name'],
                    'color': color
                })
        
    except requests.exceptions.RequestException:
        # Usar dados simulados em caso de erro
        flash("Não foi possível obter dados atualizados da API. Exibindo dados simulados.", "warning")
    
    return render_template(
        'dashboard.html',
        stats=stats,
        chart_data=chart_data,
        recent_conversations=recent_conversations,
        top_agents=top_agents
    )

# Filtro para formatar datas
@dashboard_bp.app_template_filter('datetime')
def format_datetime(value, format='%d/%m/%Y %H:%M'):
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return value
    return value.strftime(format)