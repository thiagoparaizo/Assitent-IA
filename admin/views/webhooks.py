# Criar arquivo admin/views/webhooks.py

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
import requests
import json

from admin.config import Config

webhooks_bp = Blueprint('webhooks', __name__, url_prefix='/webhooks')

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

@webhooks_bp.route('/')
@login_required
def index():
    """Lista de webhooks configurados."""
    webhooks = []
    
    print("Lista de webhooks configurados...")
    
    try:
        tenant_id = current_user.tenant_id if current_user.tenant_id else 1
        print( "Tenant ID:", tenant_id )
        response = requests.get(
            f"{Config.API_URL}/webhook?tenant_id={tenant_id}",
            headers=get_api_headers(),
            timeout=5
        )
        
        if response.status_code == 200:
            webhooks = response.json()
    except Exception as e:
        flash(f"Erro ao obter webhooks: {e}", "danger")
    
    return render_template('webhooks/index.html', webhooks=webhooks)

@webhooks_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """Criar novo webhook."""
    if request.method == 'POST':
        webhook_data = {
            'url': request.form.get('url'),
            'secret': request.form.get('secret'),
            'events': request.form.getlist('events'),
            'device_ids': [int(id) for id in request.form.getlist('device_ids')],
            'tenant_id': current_user.tenant_id if current_user.tenant_id else 1,
            'enabled': 'enabled' in request.form
        }
        
        try:
            response = requests.post(
                f"{Config.API_URL}/webhook/create",
                headers=get_api_headers(),
                json=webhook_data,
                timeout=10
            )
            
            if response.status_code == 200:
                flash("Webhook criado com sucesso!", "success")
                return redirect(url_for('webhooks.index'))
            else:
                error_detail = "Erro desconhecido"
                try:
                    error_data = response.json()
                    error_detail = error_data.get('error', str(response.status_code))
                except:
                    error_detail = f"Erro {response.status_code}"
                
                flash(f"Erro ao criar webhook: {error_detail}", "danger")
                
        except requests.exceptions.RequestException as e:
            flash(f"Erro ao criar webhook: {e}", "danger")
    
    # Obter lista de dispositivos para seleção
    devices = []
    try:
        tenant_id = current_user.tenant_id if current_user.tenant_id else 1
        response = requests.get(
            f"{Config.API_URL}/whatsapp/devices/?tenant_id={tenant_id}",
            headers=get_api_headers(),
            timeout=5
        )
        
        if response.status_code == 200:
            devices = response.json()
    except Exception as e:
        flash(f"Erro ao obter dispositivos: {e}", "danger")
    
    # Tipos de eventos disponíveis
    event_types = [
        {"value": "*", "name": "Todos os eventos"},
        {"value": "*events.Connected", "name": "Conexão estabelecida"},
        {"value": "*events.Disconnected", "name": "Dispositivo desconectado"},
        {"value": "*events.LoggedOut", "name": "Logout realizado"},
        {"value": "*events.Message", "name": "Mensagem recebida"},
        {"value": "*events.Receipt", "name": "Confirmação de recebimento"},
        {"value": "*events.Presence", "name": "Atualização de presença"},
    ]
    
    return render_template('webhooks/create.html', devices=devices, event_types=event_types)

@webhooks_bp.route('/<string:webhook_id>/delete', methods=['POST'])
@login_required
def delete(webhook_id):
    """Excluir webhook."""
    try:
        response = requests.delete(
            f"{Config.API_URL}/webhook/{webhook_id}",
            headers=get_api_headers(),
            timeout=5
        )
        
        if response.status_code == 200:
            flash("Webhook excluído com sucesso!", "success")
        else:
            error_detail = "Erro desconhecido"
            try:
                error_data = response.json()
                error_detail = error_data.get('error', str(response.status_code))
            except:
                error_detail = f"Erro {response.status_code}"
            
            flash(f"Erro ao excluir webhook: {error_detail}", "danger")
            
    except requests.exceptions.RequestException as e:
        flash(f"Erro ao excluir webhook: {e}", "danger")
        
    return redirect(url_for('webhooks.index'))

@webhooks_bp.route('/<string:webhook_id>/test', methods=['POST'])
@login_required
def test(webhook_id):
    """Testar webhook."""
    try:
        response = requests.post(
            f"{Config.API_URL}/webhook/{webhook_id}/test",
            headers=get_api_headers(),
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('status') == 'success':
                flash("Teste de webhook enviado com sucesso!", "success")
            else:
                flash(f"Erro no teste de webhook: {result.get('message')}", "warning")
        else:
            error_detail = "Erro desconhecido"
            try:
                error_data = response.json()
                error_detail = error_data.get('error', str(response.status_code))
            except:
                error_detail = f"Erro {response.status_code}"
            
            flash(f"Erro ao testar webhook: {error_detail}", "danger")
            
    except requests.exceptions.RequestException as e:
        flash(f"Erro ao testar webhook: {e}", "danger")
        
    return redirect(url_for('webhooks.index'))

@webhooks_bp.route('/<string:webhook_id>/logs')
@login_required
def logs(webhook_id):
    """Visualizar logs de entrega de webhook."""
    logs = []
    
    try:
        response = requests.get(
            f"{Config.API_URL}/webhook/{webhook_id}/logs",
            headers=get_api_headers(),
            timeout=5
        )
        
        if response.status_code == 200:
            logs = response.json()
    except Exception as e:
        flash(f"Erro ao obter logs: {e}", "danger")
    
    return render_template('webhooks/logs.html', logs=logs, webhook_id=webhook_id)