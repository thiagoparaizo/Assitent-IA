from flask import Blueprint, flash, render_template
from flask_login import current_user, login_required
import requests
from datetime import datetime, timedelta
import logging

from admin.config import Config

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

# Configure logging
logger = logging.getLogger(__name__)

def get_api_headers():
    """Generate API headers with authentication info"""
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
    """Dashboard main page with statistics and charts"""
    # Initialize data structures with default values
    stats = {
        'active_agents': 0,
        'conversations_today': 0,
        'knowledge_count': 0,
        'whatsapp_devices': 0
    }
    
    # Default for dates (last 7 days)
    today = datetime.now()
    dates = [(today - timedelta(days=i)).strftime('%d/%m') for i in range(6, -1, -1)]
    
    # Default chart data
    chart_data = {
        'dates': dates,
        'conversations': [0] * 7,
        'messages': [0] * 7,
        'agent_names': ['Agente Geral'],
        'agent_counts': [1],
        'agent_colors': ['#4e73df'],
        'agent_hover_colors': ['#2e59d9'],
    }
    
    # Default empty conversation list
    recent_conversations = []
    
    # Default top agents
    top_agents = []
    
    try:
        # 1. Get basic statistics
        logger.info("Fetching dashboard statistics")
        stats_response = requests.get(
            f"{Config.API_URL}/dashboard/stats",
            headers=get_api_headers(),
            timeout=5
        )
        
        if stats_response.status_code == 200:
            stats = stats_response.json()
            logger.info(f"Successfully fetched dashboard stats: {stats}")
        else:
            logger.warning(f"Failed to fetch dashboard stats: {stats_response.status_code}")
            if stats_response.status_code != 404:
                flash(f"Erro ao obter estatísticas: {stats_response.status_code}", "warning")
        
        # 2. Get chart data
        logger.info("Fetching dashboard chart data")
        charts_response = requests.get(
            f"{Config.API_URL}/dashboard/charts",
            headers=get_api_headers(),
            timeout=5
        )
        
        if charts_response.status_code == 200:
            chart_data = charts_response.json()
            logger.info("Successfully fetched chart data")
        else:
            logger.warning(f"Failed to fetch chart data: {charts_response.status_code}")
            if charts_response.status_code != 404:
                flash(f"Erro ao obter dados dos gráficos: {charts_response.status_code}", "warning")
        
        # 3. Get recent conversations
        logger.info("Fetching recent conversations")
        conversations_response = requests.get(
            f"{Config.API_URL}/dashboard/recent-conversations",
            headers=get_api_headers(),
            timeout=5
        )
        
        if conversations_response.status_code == 200:
            recent_conversations = conversations_response.json()
            logger.info(f"Successfully fetched {len(recent_conversations)} recent conversations")
        else:
            logger.warning(f"Failed to fetch recent conversations: {conversations_response.status_code}")
            if conversations_response.status_code != 404:
                flash(f"Erro ao obter conversas recentes: {conversations_response.status_code}", "warning")
        
        # 4. Extract top agents from chart data for legend display
        top_agents = []
        if 'agent_names' in chart_data and 'agent_colors' in chart_data:
            for i, name in enumerate(chart_data['agent_names']):
                if i < len(chart_data['agent_colors']):
                    top_agents.append({
                        'name': name,
                        'color': chart_data['agent_colors'][i]
                    })
        
    except requests.exceptions.RequestException as e:
        # Connection error
        logger.error(f"API connection error: {e}")
        flash(f"Erro ao conectar com a API: {e}", "danger")
    except Exception as e:
        # Unexpected error
        logger.exception(f"Unexpected error in dashboard view: {e}")
        flash(f"Erro inesperado: {e}", "danger")
    
    return render_template(
        'dashboard.html',
        stats=stats,
        chart_data=chart_data,
        recent_conversations=recent_conversations,
        top_agents=top_agents
    )

# Filter to format dates
@dashboard_bp.app_template_filter('datetime')
def format_datetime(value, format='%d/%m/%Y %H:%M'):
    """Format datetime values for display"""
    if isinstance(value, str):
        try:
            # Try to parse ISO format date
            value = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            return value
    return value.strftime(format)