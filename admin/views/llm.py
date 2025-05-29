# admin/views/llm.py
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
import requests
from datetime import datetime

from admin.config import Config

import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("admin.views.llm")


# Criar o blueprint
llm_bp = Blueprint('llm', __name__, url_prefix='/llm')

def get_api_headers():
    # return {
    #     'Content-Type': 'application/json',
    #     'Authorization': f'Bearer {Config.API_TOKEN}',
    #     'X-Tenant-ID': str(current_user.tenant_id) if current_user.tenant_id else ''
    # }
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

# Helpers
def get_current_user_api_headers():
    headers = {
        'Content-Type': 'application/json',
    }
    
    if hasattr(current_user, 'token') and current_user.token:
        headers['Authorization'] = f'Bearer {current_user.token}'
    
    return headers

@llm_bp.route('/')
@login_required
def index():
    """Lista todos os provedores LLM."""
    # Verificar se usuário é admin
    if not current_user.is_superuser:
        flash('Você não tem permissão para acessar esta página.', 'danger')
        return redirect(url_for('dashboard.index'))
    
    # Obter lista de provedores
    providers = []
    try:
        response = requests.get(
            f"{Config.API_URL}/llm/providers/",
            headers=get_current_user_api_headers(),
            timeout=5
        )
        
        if response.status_code == 200:
            providers = response.json()
        else:
            flash(f"Erro ao carregar provedores LLM: {response.status_code}", "danger")
    except requests.exceptions.RequestException as e:
        flash(f"Erro ao conectar com a API: {str(e)}", "danger")
    
    return render_template('llm/provider_list.html', providers=providers)

@llm_bp.route('/providers/create', methods=['GET', 'POST'])
@login_required
def create_provider():
    """Cria um novo provedor LLM."""
    # Verificar se usuário é admin
    if not current_user.is_superuser:
        flash('Você não tem permissão para acessar esta página.', 'danger')
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        # Obter dados do formulário
        provider_data = {
            'name': request.form.get('name'),
            'provider_type': request.form.get('provider_type'),
            'description': request.form.get('description'),
            'base_url': request.form.get('base_url'),
            'is_active': 'is_active' in request.form
        }
        
        try:
            # Chamar API para criar provedor
            response = requests.post(
                f"{Config.API_URL}/llm/providers/",
                headers=get_current_user_api_headers(),
                json=provider_data,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                flash('Provedor LLM criado com sucesso!', 'success')
                return redirect(url_for('llm.index'))
            else:
                error_detail = "Erro desconhecido"
                try:
                    error_data = response.json()
                    error_detail = error_data.get('detail', str(response.status_code))
                except:
                    error_detail = f"Erro {response.status_code}"
                
                flash(f"Erro ao criar provedor LLM: {error_detail}", "danger")
        except requests.exceptions.RequestException as e:
            flash(f"Erro ao conectar com a API: {str(e)}", "danger")
    
    # Tipos de provedor disponíveis
    provider_types = [
        {"id": "openai", "name": "OpenAI"},
        {"id": "gemini", "name": "Google Gemini"},
        {"id": "deepseek", "name": "DeepSeek AI"},
        {"id": "anthropic", "name": "Anthropic (Claude)"},
        {"id": "mistral", "name": "Mistral AI"},
        {"id": "ollama", "name": "Ollama (Self-hosted)"},
        {"id": "custom", "name": "Custom / Other"}
    ]
    
    return render_template('llm/provider_create.html', provider_types=provider_types)

@llm_bp.route('/providers/<int:provider_id>')
@login_required
def view_provider(provider_id):
    """Ver detalhes de um provedor LLM."""
    # Verificar se usuário é admin
    if not current_user.is_superuser:
        flash('Você não tem permissão para acessar esta página.', 'danger')
        return redirect(url_for('dashboard.index'))
    
    # Obter provedor
    provider = None
    models = []
    try:
        # Obter detalhes do provedor
        provider_response = requests.get(
            f"{Config.API_URL}/llm/providers/{provider_id}",
            headers=get_current_user_api_headers(),
            timeout=5
        )
        
        if provider_response.status_code == 200:
            provider = provider_response.json()
            
            # Obter modelos do provedor
            models_response = requests.get(
                f"{Config.API_URL}/llm/models?provider_id={provider_id}",
                headers=get_current_user_api_headers(),
                timeout=5
            )
            
            if models_response.status_code == 200:
                models = models_response.json()
        else:
            flash(f"Erro ao carregar provedor LLM: {provider_response.status_code}", "danger")
            return redirect(url_for('llm.index'))
    except requests.exceptions.RequestException as e:
        flash(f"Erro ao conectar com a API: {str(e)}", "danger")
        return redirect(url_for('llm.index'))
    
    if not provider:
        flash('Provedor LLM não encontrado.', 'danger')
        return redirect(url_for('llm.index'))
    
    return render_template('llm/provider_view.html', provider=provider, models=models)

# Rotas similares para edição e exclusão de providers...

# Rotas para gerenciamento de modelos
@llm_bp.route('/models')
@login_required
def list_models():
    """Lista todos os modelos LLM."""
    # Verificar se usuário é admin
    if not current_user.is_superuser:
        flash('Você não tem permissão para acessar esta página.', 'danger')
        return redirect(url_for('dashboard.index'))
    
    # Obter lista de modelos
    models = []
    providers = []
    try:
        # Obter modelos
        models_response = requests.get(
            f"{Config.API_URL}/llm/models/",
            headers=get_current_user_api_headers(),
            timeout=5
        )
        
        if models_response.status_code == 200:
            models = models_response.json()
        else:
            flash(f"Erro ao carregar modelos LLM: {models_response.status_code}", "danger")
        
        # Obter provedores para filtros
        providers_response = requests.get(
            f"{Config.API_URL}/llm/providers/",
            headers=get_current_user_api_headers(),
            timeout=5
        )
        
        if providers_response.status_code == 200:
            providers = providers_response.json()
    except requests.exceptions.RequestException as e:
        flash(f"Erro ao conectar com a API: {str(e)}", "danger")
    
    return render_template('llm/model_list.html', models=models, providers=providers)

# Rotas similares para criação, edição e exclusão de modelos...

# Endpoint para uso AJAX para carregar modelos de um provedor
@llm_bp.route('/api/models-by-provider/<int:provider_id>')
@login_required
def get_models_by_provider(provider_id):
    """API para buscar modelos de um provedor específico (usado em formulários)."""
    try:
        response = requests.get(
            f"{Config.API_URL}/llm/models?provider_id={provider_id}",
            headers=get_current_user_api_headers(),
            timeout=5
        )
        
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({"error": f"Status {response.status_code}"}), 400
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500
    
@llm_bp.route('/api/models', methods=['GET'])
@login_required
def api_get_models():
    """API interna para obter modelos de um provedor via AJAX."""
    provider_id = request.args.get('provider_id', type=int)
    
    if not provider_id:
        return jsonify([])
    
    try:
        response = requests.get(
            f"{Config.API_URL}/llm/models?provider_id={provider_id}",
            headers=get_current_user_api_headers(),
            timeout=5
        )
        
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({"error": f"Status {response.status_code}"}), 400
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500
    
@llm_bp.route('/providers/<int:provider_id>/delete', methods=['POST'])
@login_required
def delete_provider(provider_id):
    """Exclui um provedor LLM."""
    # Verificar se usuário é admin
    if not current_user.is_superuser:
        flash('Você não tem permissão para acessar esta página.', 'danger')
        return redirect(url_for('dashboard.index'))
    
    try:
        # Chamar API para excluir provedor
        response = requests.delete(
            f"{Config.API_URL}/llm/providers/{provider_id}",
            headers=get_current_user_api_headers(),
            timeout=10
        )
        
        if response.status_code == 200:
            flash('Provedor LLM excluído com sucesso!', 'success')
        else:
            error_detail = "Erro desconhecido"
            try:
                error_data = response.json()
                error_detail = error_data.get('detail', str(response.status_code))
            except:
                error_detail = f"Erro {response.status_code}"
            
            flash(f"Erro ao excluir provedor LLM: {error_detail}", "danger")
    except requests.exceptions.RequestException as e:
        flash(f"Erro ao conectar com a API: {str(e)}", "danger")
    
    return redirect(url_for('llm.index'))


@llm_bp.route('/providers/<int:provider_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_provider(provider_id):
    """Edita um provedor LLM existente."""
    # Verificar se usuário é admin
    if not current_user.is_superuser:
        flash('Você não tem permissão para acessar esta página.', 'danger')
        return redirect(url_for('dashboard.index'))
    
    # Obter provedor
    provider = None
    try:
        response = requests.get(
            f"{Config.API_URL}/llm/providers/{provider_id}",
            headers=get_current_user_api_headers(),
            timeout=5
        )
        
        if response.status_code == 200:
            provider = response.json()
        else:
            flash(f"Erro ao carregar provedor LLM: {response.status_code}", "danger")
            return redirect(url_for('llm.index'))
    except requests.exceptions.RequestException as e:
        flash(f"Erro ao conectar com a API: {str(e)}", "danger")
        return redirect(url_for('llm.index'))
    
    if not provider:
        flash('Provedor LLM não encontrado.', 'danger')
        return redirect(url_for('llm.index'))
    
    if request.method == 'POST':
        # Obter dados do formulário
        provider_data = {
            'name': request.form.get('name'),
            'description': request.form.get('description'),
            'base_url': request.form.get('base_url'),
            'is_active': 'is_active' in request.form
        }
        
        try:
            # Chamar API para atualizar provedor
            response = requests.put(
                f"{Config.API_URL}/llm/providers/{provider_id}",
                headers=get_current_user_api_headers(),
                json=provider_data,
                timeout=10
            )
            
            if response.status_code == 200:
                flash('Provedor LLM atualizado com sucesso!', 'success')
                return redirect(url_for('llm.view_provider', provider_id=provider_id))
            else:
                error_detail = "Erro desconhecido"
                try:
                    error_data = response.json()
                    error_detail = error_data.get('detail', str(response.status_code))
                except:
                    error_detail = f"Erro {response.status_code}"
                
                flash(f"Erro ao atualizar provedor LLM: {error_detail}", "danger")
        except requests.exceptions.RequestException as e:
            flash(f"Erro ao conectar com a API: {str(e)}", "danger")
    
    # Tipos de provedor disponíveis (somente para referência, não pode ser alterado na edição)
    provider_types = [
        {"id": "openai", "name": "OpenAI"},
        {"id": "gemini", "name": "Google Gemini"},
        {"id": "deepseek", "name": "DeepSeek AI"},
        {"id": "anthropic", "name": "Anthropic (Claude)"},
        {"id": "mistral", "name": "Mistral AI"},
        {"id": "ollama", "name": "Ollama (Self-hosted)"},
        {"id": "custom", "name": "Custom / Other"}
    ]
    
    # Obter o nome legível do tipo de provedor
    provider_type_name = provider['provider_type']
    for type_info in provider_types:
        if type_info['id'] == provider['provider_type']:
            provider_type_name = type_info['name']
            break
    
    return render_template('llm/provider_edit.html', 
                           provider=provider, 
                           provider_type_name=provider_type_name,
                           provider_types=provider_types)
    

@llm_bp.route('/models/create', methods=['GET', 'POST'])
@login_required
def create_model():
    """Cria um novo modelo LLM."""
    # Verificar se usuário é admin
    if not current_user.is_superuser:
        flash('Você não tem permissão para acessar esta página.', 'danger')
        return redirect(url_for('dashboard.index'))
    
    # Parâmetro opcional provider_id para pré-selecionar o provedor
    selected_provider_id = request.args.get('provider_id', type=int)
    
    # Obter lista de provedores
    providers = []
    try:
        response = requests.get(
            f"{Config.API_URL}/llm/providers/",
            headers=get_current_user_api_headers(),
            timeout=5
        )
        
        if response.status_code == 200:
            providers = response.json()
        else:
            flash(f"Erro ao carregar provedores LLM: {response.status_code}", "danger")
            return redirect(url_for('llm.list_models'))
    except requests.exceptions.RequestException as e:
        flash(f"Erro ao conectar com a API: {str(e)}", "danger")
        return redirect(url_for('llm.list_models'))
    
    if request.method == 'POST':
        # Obter dados do formulário
        provider_id = request.form.get('provider_id', type=int)
        
        if not provider_id:
            flash("É necessário selecionar um provedor.", "danger")
            return render_template('llm/model_create.html', providers=providers, selected_provider_id=selected_provider_id)
            
        model_data = {
            'provider_id': provider_id,
            'name': request.form.get('name'),
            'model_id': request.form.get('model_id'),
            'max_tokens': request.form.get('max_tokens', type=int),
            'default_temperature': request.form.get('default_temperature', type=float, default=0.7),
            'cost_per_1k_tokens': request.form.get('cost_per_1k_tokens', type=float, default=0.0),
            'supports_functions': 'supports_functions' in request.form,
            'supports_vision': 'supports_vision' in request.form,
            'is_active': 'is_active' in request.form
        }
        
        try:
            # Chamar API para criar modelo
            response = requests.post(
                f"{Config.API_URL}/llm/models/",
                headers=get_current_user_api_headers(),
                json=model_data,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                flash('Modelo LLM criado com sucesso!', 'success')
                
                # Redirecionar para a página do provedor
                return redirect(url_for('llm.view_provider', provider_id=provider_id))
            else:
                error_detail = "Erro desconhecido"
                try:
                    error_data = response.json()
                    error_detail = error_data.get('detail', str(response.status_code))
                except:
                    error_detail = f"Erro {response.status_code}"
                
                flash(f"Erro ao criar modelo LLM: {error_detail}", "danger")
        except requests.exceptions.RequestException as e:
            flash(f"Erro ao conectar com a API: {str(e)}", "danger")
    
    # Renderizar formulário
    return render_template('llm/model_create.html', providers=providers, selected_provider_id=selected_provider_id)

@llm_bp.route('/models/<int:model_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_model(model_id):
    """Edita um modelo LLM existente."""
    # Verificar se usuário é admin
    if not current_user.is_superuser:
        flash('Você não tem permissão para acessar esta página.', 'danger')
        return redirect(url_for('dashboard.index'))
    
    # Obter modelo
    model = None
    try:
        response = requests.get(
            f"{Config.API_URL}/llm/models/{model_id}",
            headers=get_current_user_api_headers(),
            timeout=5
        )
        
        if response.status_code == 200:
            model = response.json()
        else:
            flash(f"Erro ao carregar modelo LLM: {response.status_code}", "danger")
            return redirect(url_for('llm.list_models'))
    except requests.exceptions.RequestException as e:
        flash(f"Erro ao conectar com a API: {str(e)}", "danger")
        return redirect(url_for('llm.list_models'))
    
    if not model:
        flash('Modelo LLM não encontrado.', 'danger')
        return redirect(url_for('llm.list_models'))
    
    if request.method == 'POST':
        # Obter dados do formulário
        model_data = {
            'name': request.form.get('name'),
            'model_id': request.form.get('model_id'),
            'max_tokens': request.form.get('max_tokens', type=int),
            'default_temperature': request.form.get('default_temperature', type=float, default=0.7),
            'cost_per_1k_tokens': request.form.get('cost_per_1k_tokens', type=float, default=0.0),
            'supports_functions': 'supports_functions' in request.form,
            'supports_vision': 'supports_vision' in request.form,
            'is_active': 'is_active' in request.form
        }
        
        try:
            # Chamar API para atualizar modelo
            response = requests.put(
                f"{Config.API_URL}/llm/models/{model_id}",
                headers=get_current_user_api_headers(),
                json=model_data,
                timeout=10
            )
            
            if response.status_code == 200:
                flash('Modelo LLM atualizado com sucesso!', 'success')
                return redirect(url_for('llm.view_provider', provider_id=model['provider_id']))
            else:
                error_detail = "Erro desconhecido"
                try:
                    error_data = response.json()
                    error_detail = error_data.get('detail', str(response.status_code))
                except:
                    error_detail = f"Erro {response.status_code}"
                
                flash(f"Erro ao atualizar modelo LLM: {error_detail}", "danger")
        except requests.exceptions.RequestException as e:
            flash(f"Erro ao conectar com a API: {str(e)}", "danger")
    
    # Renderizar formulário
    return render_template('llm/model_edit.html', model=model)

@llm_bp.route('/models/<int:model_id>/delete', methods=['POST'])
@login_required
def delete_model(model_id):
    """Exclui um modelo LLM."""
    # Verificar se usuário é admin
    if not current_user.is_superuser:
        flash('Você não tem permissão para acessar esta página.', 'danger')
        return redirect(url_for('dashboard.index'))
    
    # Obter modelo para saber a qual provedor pertence (para redirecionamento)
    provider_id = None
    try:
        response = requests.get(
            f"{Config.API_URL}/llm/models/{model_id}",
            headers=get_current_user_api_headers(),
            timeout=5
        )
        
        if response.status_code == 200:
            model = response.json()
            provider_id = model.get('provider_id')
    except:
        pass
    
    try:
        # Chamar API para excluir modelo
        response = requests.delete(
            f"{Config.API_URL}/llm/models/{model_id}",
            headers=get_current_user_api_headers(),
            timeout=10
        )
        
        if response.status_code == 200:
            flash('Modelo LLM excluído com sucesso!', 'success')
        else:
            error_detail = "Erro desconhecido"
            try:
                error_data = response.json()
                error_detail = error_data.get('detail', str(response.status_code))
            except:
                error_detail = f"Erro {response.status_code}"
            
            flash(f"Erro ao excluir modelo LLM: {error_detail}", "danger")
    except requests.exceptions.RequestException as e:
        flash(f"Erro ao conectar com a API: {str(e)}", "danger")
    
    # Redirecionar para a página do provedor se possível, caso contrário para a lista de modelos
    if provider_id:
        return redirect(url_for('llm.view_provider', provider_id=provider_id))
    else:
        return redirect(url_for('llm.list_models'))