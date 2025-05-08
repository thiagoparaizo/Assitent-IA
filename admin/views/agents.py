# admin/views/agents.py
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
import requests
import json

from admin.config import Config

agents_bp = Blueprint('agents', __name__, url_prefix='/agents')

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
            {"id": "financeiro", "name": "Financeiro"},
            {"id": "pessoal", "name": "Pessoal"}
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
        
        # Buscar os agentes de escalação, se habilitado
        escalation_agents = []
        if agent.get('escalation_enabled') and agent.get('list_escalation_agent_ids'):
            for esc_agent_id in agent['list_escalation_agent_ids']:
                try:
                    agent_response = requests.get(
                        f"{Config.API_URL}/agents/{esc_agent_id}",
                        headers=get_api_headers(),
                        timeout=5
                    )
                    if agent_response.status_code == 200:
                        escalation_agents.append(agent_response.json())
                except Exception:
                    pass
                
        # Garantir que os campos existam, mesmo que vazios
        if 'specialties' not in agent or agent['specialties'] is None:
            agent['specialties'] = []
            
        if 'list_escalation_agent_ids' not in agent or agent['list_escalation_agent_ids'] is None:
            agent['list_escalation_agent_ids'] = []
            
    except requests.exceptions.RequestException as e:
        flash(f"Erro ao obter agente: {e}", "danger")
        return redirect(url_for('agents.index'))
        
    return render_template('agents/view.html', agent=agent,
            escalation_agents=escalation_agents)

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
            'human_escalation_contact': request.form.get('human_escalation_contact'),
            'active': 'active' in request.form,
            'specialties': request.form.getlist('specialties'),
            'escalation_enabled': 'escalation_enabled' in request.form,
            'list_escalation_agent_ids': request.form.getlist('escalation_agent_ids'),
        }
        
        agent_data["escalation_enabled"] = 'escalation_enabled' in request.form
        agent_data["list_escalation_agent_ids"] = request.form.getlist('list_escalation_agent_ids')
        
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
           
        # Buscar todos os agentes do tenant para a lista de escalação
        agents_response = requests.get(
            f"{Config.API_URL}/agents/",
            headers=get_api_headers(),
            timeout=5
        )
        agents_response.raise_for_status()
        available_agents = agents_response.json()
        
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
        #TODO ajustar
        categories = [
            {"id": "general", "name": "Geral"},
            {"id": "agendamento", "name": "Agendamento"},
            {"id": "procedimentos", "name": "Procedimentos"},
            {"id": "financeiro", "name": "Financeiro"},
            {"id": "pessoal", "name": "Pessoal"}
        ]
    
    # Obter dispositivos disponíveis
    try:
        response = requests.get(
            f"{Config.API_URL}/whatsapp/devices/",
            headers=get_api_headers(),
            params={"tenant_id": current_user.tenant_id},
            timeout=5
        )
        response.raise_for_status()
        devices = response.json()
        
        # Buscar também quais dispositivos já estão associados a este agente
        device_response = requests.get(
            f"{Config.API_URL}/agents/{agent_id}/devices",
            headers=get_api_headers(),
            timeout=5
        )
        
        if device_response.status_code == 200:
            agent_devices = device_response.json()
            
            # Adicionar flag is_active_for_agent para cada dispositivo
            for device in devices:
                device['is_active_for_agent'] = any(d['id'] == device['id'] for d in agent_devices)
                
                # Também buscar configurações de contatos para dispositivos ativos
                if device['is_active_for_agent']:
                    device_id = device['id']
                    contacts_response = requests.get(
                        f"{Config.API_URL}/agents/{agent_id}/device/{device_id}/contacts",
                        headers=get_api_headers(),
                        timeout=5
                    )
                    
                    if contacts_response.status_code == 200:
                        contacts_data = contacts_response.json()
                        device['default_behavior'] = contacts_data['default_behavior']
                        device['contacts'] = contacts_data['contacts']
                    else:
                        device['default_behavior'] = 'blacklist'
                        device['contacts'] = []
                        
        else:
            # Se não conseguir obter os dispositivos do agente, assumir que nenhum está ativo
            for device in devices:
                device['is_active_for_agent'] = False
                
    except requests.exceptions.RequestException as e:
        flash(f"Erro ao obter dispositivos: {e}", "warning")
        devices = []
        
    print(f"agent_id: {agent_id}")
    print(f"agent: {agent}")
    print(f"categories: {categories}")
    print(f"devices: {devices}")
    
    specialties_categories = {
        "healthcare": "Saúde",
        "medical_exams": "Exames Médicos",
        "health_insurance": "Planos de Saúde",
        "retail": "Varejo",
        "order_tracking": "Rastreamento de Pedidos",
        "returns": "Trocas e Devoluções",
        "sports": "Esportes e Lazer",
        "crafts": "Artesanato",
        "professional_services": "Serviços Profissionais",
        "finance": "Finanças",
        "accounting": "Contabilidade",
        "tourism": "Turismo e Viagens",
        "hotel": "Hotelaria",
        "education": "Educação",
        "courses": "Cursos",
        "real_estate": "Imobiliário",
        "rental": "Aluguel e Locação",
        "automotive": "Automotivo",
        "maintenance": "Manutenção",
        "logistics": "Logística",
        "shipping": "Envio e Entrega",
        "events": "Eventos",
        "entertainment": "Entretenimento",
        "pets": "Pet Shop",
        "veterinary": "Veterinária",
        "wellness": "Bem-estar",
        "beauty": "Beleza e Estética",
        "technology": "Tecnologia",
        "it_support": "Suporte de TI",
        "legal": "Jurídico",
        "law": "Advocacia"
    }
        
    return render_template('agents/edit.html', agent_id=agent_id, agent=agent, categories=categories, devices=devices, available_agents=available_agents, specialties_categories=specialties_categories)

@agents_bp.route('/<agent_id>/toggle_status', methods=['POST'])
@login_required
def toggle_status(agent_id):
    # Obter status atual do agente
    try:
        response = requests.get(
            f"{Config.API_URL}/agents/{agent_id}",
            headers=get_api_headers(),
            timeout=5
        )
        response.raise_for_status()
        agent = response.json()
        
        # Inverter status atual
        new_status = not agent.get('active', True)
        
        # Enviar atualização para API
        response = requests.put(
            f"{Config.API_URL}/agents/{agent_id}/status",
            headers=get_api_headers(),
            json={"active": new_status},
            timeout=5
        )
        response.raise_for_status()
        
        status_text = "ativado" if new_status else "desativado"
        flash(f"Agente {status_text} com sucesso!", "success")
    except requests.exceptions.RequestException as e:
        flash(f"Erro ao alterar status do agente: {e}", "danger")
        
    return redirect(url_for('agents.view', agent_id=agent_id))

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
    
@agents_bp.route('/<agent_id>/device/<int:device_id>/assign', methods=['POST'])
@login_required
def assign_device(agent_id, device_id):
    """Atribuir ou desatribuir um dispositivo a um agente."""
    try:
        data = request.json
        active = data.get('active', True)
        
        headers = get_api_headers()
        
        print(f"DEBUG - assign_device - agent_id: {agent_id}, device_id: {device_id}, active: {active}")
        print(f"DEBUG - assign_device - API URL: {Config.API_URL}/agents/{agent_id}/device/{device_id}/assign")
        print(f"DEBUG - assign_device - headers: {headers}")
        print(f"DEBUG - assign_device - data: {data}")
        
        response = requests.post(
            f"{Config.API_URL}/agents/{agent_id}/device/{device_id}/assign",
            headers=headers,
            json={"active": active},
            timeout=10
        )
        
        # Log the response details
        print(f"DEBUG - assign_device - response status: {response.status_code}")
        print(f"DEBUG - assign_device - response body: {response.text}")
        
        response.raise_for_status()
        return jsonify({"success": True})
    except requests.exceptions.HTTPError as e:
        print(f"DEBUG - assign_device - HTTP error: {str(e)}")
        error_detail = "Unknown error"
        try:
            error_data = e.response.json()
            error_detail = error_data.get('detail', str(e))
        except:
            error_detail = f"HTTP Error {e.response.status_code}: {e.response.text}"
        return jsonify({"success": False, "error": error_detail}), 500
    except Exception as e:
        print(f"DEBUG - assign_device - unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

@agents_bp.route('/<agent_id>/device/<int:device_id>/contacts', methods=['POST'])
@login_required
def manage_contacts(agent_id, device_id):
    """Gerenciar contatos para um dispositivo."""
    try:
        data = request.json
        behavior = data.get('default_behavior')
        contacts = data.get('contacts', [])
        
        response = requests.post(
            f"{Config.API_URL}/agents/{agent_id}/device/{device_id}/contacts",
            headers=get_api_headers(),
            json={"default_behavior": behavior, "contacts": contacts},
            timeout=10
        )
        response.raise_for_status()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@agents_bp.route('/<agent_id>/device/<int:device_id>/contacts/<contact_id>', methods=['PUT'])
@login_required
def add_contact(agent_id, device_id, contact_id):
    """Adicionar um contato à lista."""
    try:
        data = request.json
        list_type = data.get('list_type', 'blacklist')
        
        response = requests.put(
            f"{Config.API_URL}/agents/{agent_id}/device/{device_id}/contacts/{contact_id}",
            headers=get_api_headers(),
            json={"list_type": list_type},
            timeout=10
        )
        response.raise_for_status()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@agents_bp.route('/<agent_id>/device/<int:device_id>/contacts/<contact_id>', methods=['DELETE'])
@login_required
def remove_contact(agent_id, device_id, contact_id):
    """Remover um contato da lista."""
    try:
        response = requests.delete(
            f"{Config.API_URL}/agents/{agent_id}/device/{device_id}/contacts/{contact_id}",
            headers=get_api_headers(),
            timeout=10
        )
        response.raise_for_status()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500