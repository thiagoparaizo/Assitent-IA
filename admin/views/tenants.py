# admin/views/tenants.py
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
import requests
from datetime import datetime

from admin.config import Config

import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("admin.views.tenants")

tenants_bp = Blueprint('tenants', __name__, url_prefix='/tenants')

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

@tenants_bp.route('/')
@login_required
def index():
    """List all tenants."""
    # Check if user is superuser (only superusers can manage tenants)
    if not current_user.is_superuser:
        flash('Você não tem permissão para acessar esta página.', 'danger')
        return redirect(url_for('dashboard.index'))
    
    tenants = []
    try:
        response = requests.get(
            f"{Config.API_URL}/tenants/",
            headers=get_api_headers(),
            timeout=5
        )
        
        if response.status_code == 200:
            tenants = response.json()
            
            # Augment tenants with user count
            for tenant in tenants:
                # Get user count
                try:
                    user_response = requests.get(
                        f"{Config.API_URL}/tenants/{tenant['id']}/user/count",
                        headers=get_api_headers(),
                        timeout=3
                    )
                    if user_response.status_code == 200:
                        tenant['user_count'] = user_response.json()['count']
                    else:
                        tenant['user_count'] = 0
                except:
                    tenant['user_count'] = 0
        else:
            flash(f"Erro ao carregar tenants: {response.status_code}", "danger")
    except requests.exceptions.RequestException as e:
        flash(f"Erro ao conectar com a API: {str(e)}", "danger")
    
    return render_template('tenants/index.html', tenants=tenants)

@tenants_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """Create a new tenant."""
    # Check if user is superuser
    if not current_user.is_superuser:
        flash('Você não tem permissão para acessar esta página.', 'danger')
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        # Get form data
        tenant_data = {
            'name': request.form.get('name'),
            'description': request.form.get('description'),
            'is_active': 'is_active' in request.form
        }
        
        try:
            # Call API to create tenant
            response = requests.post(
                f"{Config.API_URL}/tenants/",
                headers=get_api_headers(),
                json=tenant_data,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                flash('Tenant criado com sucesso!', 'success')
                return redirect(url_for('tenants.index'))
            else:
                error_detail = "Erro desconhecido"
                try:
                    error_data = response.json()
                    error_detail = error_data.get('detail', str(response.status_code))
                except:
                    error_detail = f"Erro {response.status_code}"
                
                flash(f"Erro ao criar tenant: {error_detail}", "danger")
        except requests.exceptions.RequestException as e:
            flash(f"Erro ao conectar com a API: {str(e)}", "danger")
    
    return render_template('tenants/create.html')

@tenants_bp.route('/<int:tenant_id>')
@login_required
def view(tenant_id):
    """View tenant details."""
    # Check if user is superuser or belongs to this tenant
    if not current_user.is_superuser and current_user.tenant_id != int(tenant_id):
        flash('Você não tem permissão para acessar esta página.', 'danger')
        return redirect(url_for('dashboard.index'))
    
    tenant = None
    users = []
    devices = []
    agents = []
    webhooks = []
    
    try:
        # Get tenant details
        response = requests.get(
            f"{Config.API_URL}/tenants/{tenant_id}",
            headers=get_api_headers(),
            timeout=5
        )
        
        if response.status_code == 200:
            tenant = response.json()
            
            # Get tenant users - ATUALIZADO
            try:
                users_response = requests.get(
                    f"{Config.API_URL}/user/",
                    headers=get_api_headers(),
                    params={"tenant_id": tenant_id},  # Filtrar por tenant
                    timeout=3
                )
                if users_response.status_code == 200:
                    users = users_response.json()
                    # Add users to tenant object
                    tenant['users'] = users
                    print(f"Loaded {len(users)} users for tenant {tenant_id}")  # Debug
                else:
                    print(f"Failed to load users: {users_response.status_code}")  # Debug
                    tenant['users'] = []
            except Exception as e:
                print(f"Error loading users: {e}")  # Debug
                tenant['users'] = []
            
            # Get tenant devices
            try:
                devices_response = requests.get(
                    f"{Config.API_URL}/whatsapp/devices/?tenant_id={tenant_id}",
                    headers=get_api_headers(),
                    timeout=3
                )
                if devices_response.status_code == 200:
                    devices = devices_response.json()
                    # Add device count to tenant object
                    tenant['device_count'] = len(devices)
                else:
                    tenant['device_count'] = 0
            except:
                tenant['device_count'] = 0
            
            # Get tenant agents
            try:
                agents_response = requests.get(
                    f"{Config.API_URL}/agents/",
                    headers=get_api_headers(),
                    params={"tenant_id": tenant_id},  # Se a API suportar filtro por tenant
                    timeout=3
                )
                if agents_response.status_code == 200:
                    all_agents = agents_response.json()
                    # Filtrar agentes do tenant específico
                    agents = [agent for agent in all_agents if agent.get('tenant_id') == tenant_id]
                    # Add agent count to tenant object
                    tenant['agent_count'] = len(agents)
                else:
                    tenant['agent_count'] = 0
            except:
                tenant['agent_count'] = 0
            
            # Get tenant webhooks
            try:
                webhooks_response = requests.get(
                    f"{Config.API_URL}/webhook?tenant_id={tenant_id}",
                    headers=get_api_headers(),
                    timeout=3
                )
                if webhooks_response.status_code == 200:
                    webhooks = webhooks_response.json()
            except:
                pass
        else:
            flash(f"Erro ao carregar tenant: {response.status_code}", "danger")
            return redirect(url_for('tenants.index'))
    except requests.exceptions.RequestException as e:
        flash(f"Erro ao conectar com a API: {str(e)}", "danger")
        return redirect(url_for('tenants.index'))
    
    if not tenant:
        flash('Tenant não encontrado.', 'danger')
        return redirect(url_for('tenants.index'))
    
    return render_template('tenants/view.html', tenant=tenant, devices=devices, agents=agents, webhooks=webhooks)

@tenants_bp.route('/<int:tenant_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(tenant_id):
    """Edit tenant details."""
    # Check if user is superuser
    if not current_user.is_superuser:
        flash('Você não tem permissão para acessar esta página.', 'danger')
        return redirect(url_for('dashboard.index'))
    
    tenant = None
    
    # Get tenant details
    try:
        response = requests.get(
            f"{Config.API_URL}/tenants/{tenant_id}",
            headers=get_api_headers(),
            timeout=5
        )
        
        if response.status_code == 200:
            tenant = response.json()
        else:
            flash(f"Erro ao carregar tenant: {response.status_code}", "danger")
            return redirect(url_for('tenants.index'))
    except requests.exceptions.RequestException as e:
        flash(f"Erro ao conectar com a API: {str(e)}", "danger")
        return redirect(url_for('tenants.index'))
    
    if not tenant:
        flash('Tenant não encontrado.', 'danger')
        return redirect(url_for('tenants.index'))
    
    if request.method == 'POST':
        # Get form data
        tenant_data = {
            'name': request.form.get('name'),
            'description': request.form.get('description'),
            'is_active': 'is_active' in request.form,
            'default_llm_provider_id': request.form.get('default_llm_provider_id') or None,
            'default_llm_model_id': request.form.get('default_llm_model_id') or None,
            'llm_api_key': request.form.get('llm_api_key') or None
        }
        
        try:
            # Call API to update tenant
            response = requests.put(
                f"{Config.API_URL}/tenants/{tenant_id}",
                headers=get_api_headers(),
                json=tenant_data,
                timeout=10
            )
            
            if response.status_code == 200:
                flash('Tenant atualizado com sucesso!', 'success')
                return redirect(url_for('tenants.view', tenant_id=tenant_id))
            else:
                error_detail = "Erro desconhecido"
                try:
                    error_data = response.json()
                    error_detail = error_data.get('detail', str(response.status_code))
                except:
                    error_detail = f"Erro {response.status_code}"
                
                flash(f"Erro ao atualizar tenant: {error_detail}", "danger")
        except requests.exceptions.RequestException as e:
            flash(f"Erro ao conectar com a API: {str(e)}", "danger")
    
    # Obter a lista de provedores LLM disponíveis
    llm_providers = []
    try:
        providers_response = requests.get(
            f"{Config.API_URL}/llm/providers",
            headers=get_api_headers(),
            timeout=5
        )
        
        if providers_response.status_code == 200:
            # Filtrar apenas provedores ativos
            all_providers = providers_response.json()
            llm_providers = [p for p in all_providers if p.get('is_active', False)]
    except:
        # Se não for possível obter os provedores, continuar com lista vazia
        pass
    
    # Add additional metrics
    try:
        # Get user count
        user_response = requests.get(
            f"{Config.API_URL}/tenants/{tenant_id}/user/count",
            headers=get_api_headers(),
            timeout=3
        )
        if user_response.status_code == 200:
            tenant['user_count'] = user_response.json()['count']
        else:
            tenant['user_count'] = 0
            
        # Get device count
        device_response = requests.get(
            f"{Config.API_URL}/whatsapp/devices/count?tenant_id={tenant_id}",
            headers=get_api_headers(),
            timeout=3
        )
        if device_response.status_code == 200:
            tenant['device_count'] = device_response.json()['count']
        else:
            tenant['device_count'] = 0
            
        # Get agent count
        agent_response = requests.get(
            f"{Config.API_URL}/agents/count?tenant_id={tenant_id}",
            headers=get_api_headers(),
            timeout=3
        )
        if agent_response.status_code == 200:
            tenant['agent_count'] = agent_response.json()['count']
        else:
            tenant['agent_count'] = 0
    except:
        tenant['user_count'] = 0
        tenant['device_count'] = 0
        tenant['agent_count'] = 0
    
    return render_template('tenants/edit.html', tenant=tenant, llm_providers=llm_providers)

@tenants_bp.route('/<int:tenant_id>/delete', methods=['POST'])
@login_required
def delete(tenant_id):
    """Delete a tenant."""
    # Check if user is superuser
    if not current_user.is_superuser:
        flash('Você não tem permissão para acessar esta página.', 'danger')
        return redirect(url_for('dashboard.index'))
    
    try:
        # Call API to delete tenant
        response = requests.delete(
            f"{Config.API_URL}/tenants/{tenant_id}",
            headers=get_api_headers(),
            timeout=10
        )
        
        if response.status_code == 200:
            flash('Tenant excluído com sucesso!', 'success')
        else:
            error_detail = "Erro desconhecido"
            try:
                error_data = response.json()
                error_detail = error_data.get('detail', str(response.status_code))
            except:
                error_detail = f"Erro {response.status_code}"
            
            flash(f"Erro ao excluir tenant: {error_detail}", "danger")
    except requests.exceptions.RequestException as e:
        flash(f"Erro ao conectar com a API: {str(e)}", "danger")
    
    return redirect(url_for('tenants.index'))

@tenants_bp.route('/api/llm/models')
@login_required
def api_get_llm_models():
    """API para buscar modelos LLM para um provedor específico (usado em formulários)."""
    provider_id = request.args.get('provider_id', type=int)
    
    if not provider_id:
        return jsonify([])
    
    try:
        response = requests.get(
            f"{Config.API_URL}/llm/models?provider_id={provider_id}",
            headers=get_api_headers(),
            timeout=5
        )
        
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({"error": f"Status {response.status_code}"}), 400
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500