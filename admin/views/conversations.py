# admin/views/conversations.py
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
import requests
import json
from datetime import datetime

from admin.config import Config

conversations_bp = Blueprint('conversations', __name__, url_prefix='/conversations')

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

@conversations_bp.route('/')
@login_required
def index():
    """Lista de conversas ativas."""
    try:
        tenant_id = current_user.tenant_id if current_user.tenant_id else 1
        response = requests.get(
            f"{Config.API_URL}/conversations/",
            headers=get_api_headers(),
            params={"tenant_id": tenant_id, "limit": 50},
            timeout=10
        )
        
        if response.status_code == 200:
            conversations = response.json().get("conversations", [])
        else:
            flash(f"Erro ao obter conversas: {response.status_code}", "danger")
            conversations = []
    except Exception as e:
        flash(f"Erro ao conectar à API: {str(e)}", "danger")
        conversations = []
    
    return render_template('conversations/index.html', conversations=conversations)

@conversations_bp.route('/archived')
@login_required
def archived():
    """Lista de conversas arquivadas."""
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 20, type=int)
    skip = (page - 1) * limit
    
    # Filtros opcionais
    archive_reason = request.args.get('reason')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    params = {
        "skip": skip,
        "limit": limit
    }
    
    if archive_reason:
        params["archive_reason"] = archive_reason
    
    if start_date:
        params["start_date"] = start_date
    
    if end_date:
        params["end_date"] = end_date
    
    try:
        tenant_id = current_user.tenant_id if current_user.tenant_id else 1
        response = requests.get(
            f"{Config.API_URL}/conversations/archived/tenant/{tenant_id}",
            headers=get_api_headers(),
            params=params,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            archived_conversations = data.get("items", [])
            total = data.get("total", 0)
            total_pages = data.get("pages", 1)
        else:
            flash(f"Erro ao obter conversas arquivadas: {response.status_code}", "danger")
            archived_conversations = []
            total = 0
            total_pages = 1
    except Exception as e:
        flash(f"Erro ao conectar à API: {str(e)}", "danger")
        archived_conversations = []
        total = 0
        total_pages = 1
    
    return render_template(
        'conversations/archived.html', 
        conversations=archived_conversations,
        page=page,
        total_pages=total_pages,
        total=total,
        limit=limit,
        archive_reason=archive_reason,
        start_date=start_date,
        end_date=end_date
    )

@conversations_bp.route('/user/<user_id>')
@login_required
def user_conversations(user_id):
    """Lista de conversas de um usuário específico."""
    try:
        # Obter conversas ativas
        active_response = requests.get(
            f"{Config.API_URL}/conversations/",
            headers=get_api_headers(),
            params={"user_id": user_id, "limit": 10},
            timeout=10
        )
        
        if active_response.status_code == 200:
            active_conversations = active_response.json().get("conversations", [])
        else:
            flash(f"Erro ao obter conversas ativas: {active_response.status_code}", "danger")
            active_conversations = []
        
        # Obter conversas arquivadas
        archived_response = requests.get(
            f"{Config.API_URL}/conversations/archived/user/{user_id}",
            headers=get_api_headers(),
            params={"limit": 20},
            timeout=10
        )
        
        if archived_response.status_code == 200:
            archived_data = archived_response.json()
            archived_conversations = archived_data.get("items", [])
            total_archived = archived_data.get("total", 0)
        else:
            flash(f"Erro ao obter conversas arquivadas: {archived_response.status_code}", "danger")
            archived_conversations = []
            total_archived = 0
    except Exception as e:
        flash(f"Erro ao conectar à API: {str(e)}", "danger")
        active_conversations = []
        archived_conversations = []
        total_archived = 0
    
    return render_template(
        'conversations/user.html',
        user_id=user_id,
        active_conversations=active_conversations,
        archived_conversations=archived_conversations,
        total_archived=total_archived
    )

@conversations_bp.route('/<conversation_id>')
@login_required
def view(conversation_id):
    """Visualiza detalhes de uma conversa."""
    try:
        response = requests.get(
            f"{Config.API_URL}/conversations/{conversation_id}",
            headers=get_api_headers(),
            timeout=10
        )
        
        if response.status_code == 200:
            conversation = response.json()
        else:
            flash(f"Erro ao obter conversa: {response.status_code}", "danger")
            return redirect(url_for('conversations.index'))
    except Exception as e:
        flash(f"Erro ao conectar à API: {str(e)}", "danger")
        return redirect(url_for('conversations.index'))
    
    # Obter resumo da conversa, se disponível
    try:
        summary_response = requests.get(
            f"{Config.API_URL}/conversations/{conversation_id}/summary",
            headers=get_api_headers(),
            timeout=10
        )
        
        if summary_response.status_code == 200:
            summary = summary_response.json()
        else:
            summary = {"summary": "Resumo não disponível"}
    except Exception:
        summary = {"summary": "Resumo não disponível"}
    
    return render_template(
        'conversations/view.html',
        conversation=conversation,
        summary=summary
    )

@conversations_bp.route('/archived/<conversation_id>')
@login_required
def view_archived(conversation_id):
    """Visualiza detalhes de uma conversa arquivada."""
    try:
        response = requests.get(
            f"{Config.API_URL}/conversations/archived/{conversation_id}",
            headers=get_api_headers(),
            timeout=10
        )
        
        if response.status_code == 200:
            conversation = response.json()
        else:
            flash(f"Erro ao obter conversa arquivada: {response.status_code}", "danger")
            return redirect(url_for('conversations.archived'))
    except Exception as e:
        flash(f"Erro ao conectar à API: {str(e)}", "danger")
        return redirect(url_for('conversations.archived'))
    
    return render_template(
        'conversations/view_archived.html',
        conversation=conversation
    )