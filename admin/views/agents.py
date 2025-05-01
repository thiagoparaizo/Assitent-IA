# admin/views/agents.py
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
import requests
import json

from admin.config import Config

agents_bp = Blueprint('agents', __name__, url_prefix='/agents')

def get_api_headers():
    return {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {Config.API_TOKEN}',
        'X-Tenant-ID': str(current_user.tenant_id) if current_user.tenant_id else ''
    }

@agents_bp.route('/')
@login_required
def index():
    # Obter lista de agentes via API
    try:
        response = requests.get(
            f"{Config.API_URL}/agents/",
            headers=get_api_headers()
        )
        response.raise_for_status()
        agents = response.json()
    except requests.exceptions.RequestException as e:
        flash(f"Erro ao obter agentes: {e}", "danger")
        agents = []
        
    return render_template('agents/index.html', agents=agents)

@agents_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    if request.method == 'POST':
        # Obter dados do formulário
        agent_data = {
            'name': request.form.get('name'),
            'type': request.form.get('type'),
            'description': request.form.get('description'),
            'prompt': {
                'role': request.form.get('prompt_role'),
                'description': request.form.get('prompt_description'),
                'instructions': request.form.get('prompt_instructions'),
                'constraints': request.form.get('prompt_constraints', '').splitlines() if request.form.get('prompt_constraints') else None,
                'examples': json.loads(request.form.get('prompt_examples', '[]'))
            },
            'rag_categories': request.form.getlist('rag_categories'),
            'mcp_enabled': 'mcp_enabled' in request.form,
            'mcp_functions': json.loads(request.form.get('mcp_functions', '[]')),
            'human_escalation_enabled': 'human_escalation_enabled' in request.form,
            'human_escalation_contact': request.form.get('human_escalation_contact')
        }
        
        # Enviar para API
        try:
            response = requests.post(
                f"{Config.API_URL}/agents/",
                headers=get_api_headers(),
                json=agent_data,
                timeout=10
            )
            response.raise_for_status()
            flash("Agente criado com sucesso!", "success")
            return redirect(url_for('agents.index'))
        except requests.exceptions.HTTPError as e:
            error_detail = "Erro desconhecido"
            try:
                error_data = e.response.json()
                error_detail = error_data.get('detail', str(e))
            except:
                error_detail = str(e)
            flash(f"Erro ao criar agente: {error_detail}", "danger")
        except requests.exceptions.RequestException as e:
            flash(f"Erro ao criar agente: {e}", "danger")
        
    # Obter categorias de conhecimento
    try:
        response = requests.get(
            f"{Config.API_URL}/knowledge/categories",
            headers=get_api_headers(),
            timeout=5
        )
        response.raise_for_status()
        categories = response.json()['categories']
    except requests.exceptions.RequestException:
        categories = [ # TODO: Vrificar mais tarde outras categorias fixas
            {"id": "general", "name": "Geral"},
            {"id": "agendamento", "name": "Agendamento"},
            {"id": "procedimentos", "name": "Procedimentos"},
            {"id": "financeiro", "name": "Financeiro"}
        ]
        
    return render_template('agents/create.html', categories=categories)

@agents_bp.route('/<agent_id>')
@login_required
def view(agent_id):
    # Obter detalhes do agente via API
    try:
        response = requests.get(
            f"{Config.API_URL}/agents/{agent_id}",
            headers=get_api_headers(),
            timeout=5
        )
        response.raise_for_status()
        agent = response.json()
    except requests.exceptions.RequestException as e:
        flash(f"Erro ao obter agente: {e}", "danger")
        return redirect(url_for('agents.index'))
        
    return render_template('agents/view.html', agent=agent)

@agents_bp.route('/<agent_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(agent_id):
    if request.method == 'POST':
        # Obter dados do formulário
        agent_data = {
            'name': request.form.get('name'),
            'description': request.form.get('description'),
            'prompt': {
                'role': request.form.get('prompt_role'),
                'description': request.form.get('prompt_description'),
                'instructions': request.form.get('prompt_instructions'),
                'constraints': request.form.get('prompt_constraints', '').splitlines() if request.form.get('prompt_constraints') else None,
                'examples': json.loads(request.form.get('prompt_examples', '[]'))
            },
            'rag_categories': request.form.getlist('rag_categories'),
            'mcp_enabled': 'mcp_enabled' in request.form,
            'mcp_functions': json.loads(request.form.get('mcp_functions', '[]')),
            'human_escalation_enabled': 'human_escalation_enabled' in request.form,
            'human_escalation_contact': request.form.get('human_escalation_contact')
        }
        
        # Enviar para API
        try:
            response = requests.put(
                f"{Config.API_URL}/agents/{agent_id}",
                headers=get_api_headers(),
                json=agent_data,
                timeout=10
            )
            response.raise_for_status()
            flash("Agente atualizado com sucesso!", "success")
            return redirect(url_for('agents.view', agent_id=agent_id))
        except requests.exceptions.HTTPError as e:
            error_detail = "Erro desconhecido"
            try:
                error_data = e.response.json()
                error_detail = error_data.get('detail', str(e))
            except:
                error_detail = str(e)
            flash(f"Erro ao atualizar agente: {error_detail}", "danger")
        except requests.exceptions.RequestException as e:
            flash(f"Erro ao atualizar agente: {e}", "danger")
    
    # Obter detalhes do agente via API
    try:
        response = requests.get(
            f"{Config.API_URL}/agents/{agent_id}",
            headers=get_api_headers(),
            timeout=5
        )
        response.raise_for_status()
        agent = response.json()
    except requests.exceptions.RequestException as e:
        flash(f"Erro ao obter agente: {e}", "danger")
        return redirect(url_for('agents.index'))
    
    # Obter categorias de conhecimento
    try:
        response = requests.get(
            f"{Config.API_URL}/knowledge/categories",
            headers=get_api_headers(),
            timeout=5
        )
        response.raise_for_status()
        categories = response.json()['categories']
    except requests.exceptions.RequestException:
        categories = [# TODO: Vrificar mais tarde outras categorias fixas ou criar uma constante
            {"id": "general", "name": "Geral"},
            {"id": "agendamento", "name": "Agendamento"},
            {"id": "procedimentos", "name": "Procedimentos"},
            {"id": "financeiro", "name": "Financeiro"}
        ]
        
    return render_template('agents/edit.html', agent=agent, categories=categories)

@agents_bp.route('/<agent_id>/delete', methods=['POST'])
@login_required
def delete(agent_id):
    # Enviar para API
    try:
        response = requests.delete(
            f"{Config.API_URL}/agents/{agent_id}",
            headers=get_api_headers(),
            timeout=5
        )
        response.raise_for_status()
        flash("Agente removido com sucesso!", "success")
    except requests.exceptions.RequestException as e:
        flash(f"Erro ao remover agente: {e}", "danger")
        
    return redirect(url_for('agents.index'))

@agents_bp.route('/test-prompt', methods=['POST'])
@login_required
def test_prompt():
    prompt_data = request.json
    
    # Enviar para API de teste de prompt
    try:
        response = requests.post(
            f"{Config.API_URL}/agents/test-prompt",
            headers=get_api_headers(),
            json=prompt_data,
            timeout=15
        )
        response.raise_for_status()
        return jsonify(response.json())
    except requests.exceptions.RequestException as e:
        return jsonify({'error': str(e)}), 500