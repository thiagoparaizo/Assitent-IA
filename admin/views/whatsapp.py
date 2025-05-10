# admin/views/whatsapp.py
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
import requests
import json

from admin.config import Config

whatsapp_bp = Blueprint('whatsapp', __name__, url_prefix='/whatsapp')

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
        
    print(f"Headers enviados para API: {headers}")
    
    return headers

@whatsapp_bp.route('/devices')
@login_required
def devices():
    # Obter lista de dispositivos via API
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
    except requests.exceptions.RequestException as e:
        flash(f"Erro ao obter dispositivos: {e}", "danger")
    
    return render_template('whatsapp/devices.html', devices=devices)

@whatsapp_bp.route('/devices/create', methods=['GET', 'POST'])
@login_required
def create_device():
    if request.method == 'POST':
        # Obter dados do formulário
        device_data = {
            'tenant_id': current_user.tenant_id if current_user.tenant_id else 1,
            'name': request.form.get('name'),
            'description': request.form.get('description', ''),
            'phone_number': request.form.get('phone_number', '')
        }
        
        # Enviar para API
        try:
            response = requests.post(
                f"{Config.API_URL}/whatsapp/devices/",
                headers=get_api_headers(),
                json=device_data,
                timeout=10
            )
            
            if response.status_code == 200 or response.status_code == 201:
                flash("Dispositivo criado com sucesso!", "success")
                return redirect(url_for('whatsapp.devices'))
            else:
                error_detail = "Erro desconhecido"
                try:
                    error_data = response.json()
                    error_detail = error_data.get('detail', str(response.status_code))
                except:
                    error_detail = f"Erro {response.status_code}"
                
                flash(f"Erro ao criar dispositivo: {error_detail}", "danger")
                
        except requests.exceptions.RequestException as e:
            flash(f"Erro ao criar dispositivo: {e}", "danger")
    
    return render_template('whatsapp/create_device.html')

@whatsapp_bp.route('/devices/<device_id>')
@login_required
def view_device(device_id):
    # Obter detalhes do dispositivo via API
    device = None
    device_status = None
    
    try:
        # Obter informações do dispositivo
        response = requests.get(
            f"{Config.API_URL}/whatsapp/devices/{device_id}",
            headers=get_api_headers(),
            timeout=5
        )
        
        if response.status_code == 200:
            device = response.json()
            
            # Obter status do dispositivo
            status_response = requests.get(
                f"{Config.API_URL}/whatsapp/devices/{device_id}/status",
                headers=get_api_headers(),
                timeout=5
            )
            
            if status_response.status_code == 200:
                device_status = status_response.json()
            
    except requests.exceptions.RequestException as e:
        flash(f"Erro ao obter informações do dispositivo: {e}", "danger")
        return redirect(url_for('whatsapp.devices'))
    
    if not device:
        flash("Dispositivo não encontrado", "danger")
        return redirect(url_for('whatsapp.devices'))
    
    return render_template('whatsapp/view_device.html', device=device, device_status=device_status)

@whatsapp_bp.route('/devices/<device_id>/qrcode')
@login_required
def qrcode(device_id):
    # Obter QR Code do dispositivo via API
    qr_data = None
    device = None
    
    try:
        # Obter informações do dispositivo
        device_response = requests.get(
            f"{Config.API_URL}/whatsapp/devices/{device_id}",
            headers=get_api_headers(),
            timeout=5
        )
        
        if device_response.status_code == 200:
            device = device_response.json()
        
        # Obter QR Code
        response = requests.get(
            f"{Config.API_URL}/whatsapp/devices/{device_id}/qrcode",
            headers=get_api_headers(),
            timeout=10
        )
        
        if response.status_code == 200:
            qr_data = response.json()
        else:
            error_detail = "Erro desconhecido"
            try:
                error_data = response.json()
                error_detail = error_data.get('detail', str(response.status_code))
            except:
                error_detail = f"Erro {response.status_code}"
            
            flash(f"Erro ao obter QR Code: {error_detail}", "danger")
            return redirect(url_for('whatsapp.view_device', device_id=device_id))
            
    except requests.exceptions.RequestException as e:
        flash(f"Erro ao obter QR Code: {e}", "danger")
        return redirect(url_for('whatsapp.view_device', device_id=device_id))
    
    if not qr_data or not device:
        flash("Não foi possível obter QR Code", "danger")
        return redirect(url_for('whatsapp.view_device', device_id=device_id))
    
    return render_template('whatsapp/qrcode.html', qr_data=qr_data, device=device)

@whatsapp_bp.route('/devices/<device_id>/status', methods=['POST'])
@login_required
def update_status(device_id):
    # Atualizar status do dispositivo
    status = request.form.get('status')
    
    if not status:
        flash("Status não especificado", "danger")
        return redirect(url_for('whatsapp.view_device', device_id=device_id))
    
    try:
        response = requests.put(
            f"{Config.API_URL}/whatsapp/devices/{device_id}/status",
            headers=get_api_headers(),
            json={"status": status},
            timeout=5
        )
        
        if response.status_code == 200:
            flash("Status atualizado com sucesso!", "success")
        else:
            error_detail = "Erro desconhecido"
            try:
                error_data = response.json()
                error_detail = error_data.get('detail', str(response.status_code))
            except:
                error_detail = f"Erro {response.status_code}"
            
            flash(f"Erro ao atualizar status: {error_detail}", "danger")
            
    except requests.exceptions.RequestException as e:
        flash(f"Erro ao atualizar status: {e}", "danger")
        
    return redirect(url_for('whatsapp.view_device', device_id=device_id))

@whatsapp_bp.route('/devices/<device_id>/disconnect', methods=['POST', 'GET'])
@login_required
def disconnect(device_id):
    try:
        response = requests.post(
            f"{Config.API_URL}/whatsapp/devices/{device_id}/disconnect",
            headers=get_api_headers(),
            timeout=5
        )
        
        if response.status_code == 200:
            flash("Dispositivo desconectado com sucesso!", "success")
        else:
            error_detail = "Erro desconhecido"
            try:
                error_data = response.json()
                error_detail = error_data.get('detail', str(response.status_code))
            except:
                error_detail = f"Erro {response.status_code}"
            
            flash(f"Erro ao desconectar dispositivo: {error_detail}", "danger")
            
    except requests.exceptions.RequestException as e:
        flash(f"Erro ao desconectar dispositivo: {e}", "danger")
        
    return redirect(url_for('whatsapp.view_device', device_id=device_id))


@whatsapp_bp.route('/devices/<device_id>/send-message', methods=['POST'])
@login_required
def send_message(device_id):
    # Obter dados do formulário
    to = request.form.get('to')
    message = request.form.get('message')
    
    if not to or not message:
        flash("Destinatário e mensagem são obrigatórios", "danger")
        return redirect(url_for('whatsapp.get_contacts', device_id=device_id))
    
    try:
        # Enviar mensagem via API
        response = requests.post(
            f"{Config.API_URL}/whatsapp/devices/{device_id}/send",
            headers=get_api_headers(),
            json={"to": to, "message": message},
            timeout=10
        )
        
        if response.status_code == 200:
            flash("Mensagem enviada com sucesso!", "success")
        else:
            error_detail = "Erro desconhecido"
            try:
                error_data = response.json()
                error_detail = error_data.get('detail', str(response.status_code))
            except:
                error_detail = f"Erro {response.status_code}"
            
            flash(f"Erro ao enviar mensagem: {error_detail}", "danger")
    except requests.exceptions.RequestException as e:
        flash(f"Erro ao enviar mensagem: {e}", "danger")
    
    return redirect(url_for('whatsapp.get_contacts', device_id=device_id))

@whatsapp_bp.route('/devices/<device_id>/contacts')
@login_required
def get_contacts(device_id):
    # Obter lista de contatos do dispositivo via API
    contacts = {}
    try:
        response = requests.get(
            f"{Config.API_URL}/whatsapp/devices/{device_id}/contacts",
            headers=get_api_headers(),
            timeout=10
        )
        
        if response.status_code == 200:
            contacts = response.json()
        else:
            error_detail = "Erro desconhecido"
            try:
                error_data = response.json()
                error_detail = error_data.get('detail', str(response.status_code))
            except:
                error_detail = f"Erro {response.status_code}"
            
            flash(f"Erro ao obter contatos: {error_detail}", "danger")
    except requests.exceptions.RequestException as e:
        flash(f"Erro ao obter contatos: {e}", "danger")
    
    # Obter informações do dispositivo para exibir o nome
    device = None
    try:
        device_response = requests.get(
            f"{Config.API_URL}/whatsapp/devices/{device_id}",
            headers=get_api_headers(),
            timeout=5
        )
        if device_response.status_code == 200:
            device = device_response.json()
    except:
        pass
    
    return render_template('whatsapp/contacts.html', contacts=contacts, device=device, device_id=device_id)

@whatsapp_bp.route('/devices/<device_id>/groups')
@login_required
def get_groups(device_id):
    # Obter lista de grupos do dispositivo via API
    groups = []
    try:
        response = requests.get(
            f"{Config.API_URL}/whatsapp/devices/{device_id}/groups",
            headers=get_api_headers(),
            timeout=10
        )
        
        if response.status_code == 200:
            groups = response.json()
        else:
            error_detail = "Erro desconhecido"
            try:
                error_data = response.json()
                error_detail = error_data.get('detail', str(response.status_code))
            except:
                error_detail = f"Erro {response.status_code}"
            
            flash(f"Erro ao obter grupos: {error_detail}", "danger")
    except requests.exceptions.RequestException as e:
        flash(f"Erro ao obter grupos: {e}", "danger")
    
    # Obter informações do dispositivo para exibir o nome
    device = None
    try:
        device_response = requests.get(
            f"{Config.API_URL}/whatsapp/devices/{device_id}",
            headers=get_api_headers(),
            timeout=5
        )
        if device_response.status_code == 200:
            device = device_response.json()
    except:
        pass
    
    return render_template('whatsapp/groups.html', groups=groups, device=device, device_id=device_id)

@whatsapp_bp.route('/devices/<device_id>/messages/<chat_type>/<chat_id>')
@login_required
def get_messages(device_id, chat_type, chat_id):
    # Determinar se é grupo ou contato
    filter_param = request.args.get('filter', 'day')
    messages = []
    
    try:
        if chat_type == 'contact':
            url = f"{Config.API_URL}/whatsapp/devices/{device_id}/contact/{chat_id}/messages"
        else:  # grupo
            url = f"{Config.API_URL}/whatsapp/devices/{device_id}/group/{chat_id}/messages"
        
        response = requests.get(
            url,
            headers=get_api_headers(),
            params={"filter": filter_param},
            timeout=15
        )
        
        if response.status_code == 200:
            messages = response.json()
        else:
            error_detail = "Erro desconhecido"
            try:
                error_data = response.json()
                error_detail = error_data.get('detail', str(response.status_code))
            except:
                error_detail = f"Erro {response.status_code}"
            
            flash(f"Erro ao obter mensagens: {error_detail}", "danger")
    except requests.exceptions.RequestException as e:
        flash(f"Erro ao obter mensagens: {e}", "danger")
    
    # Obter informações do dispositivo e do chat
    device = None
    chat_name = chat_id
    
    try:
        device_response = requests.get(
            f"{Config.API_URL}/whatsapp/devices/{device_id}",
            headers=get_api_headers(),
            timeout=5
        )
        if device_response.status_code == 200:
            device = device_response.json()
    except:
        pass
    
    # Tentar obter nome do chat (contato ou grupo)
    try:
        if chat_type == 'contact':
            contact_response = requests.get(
                f"{Config.API_URL}/whatsapp/devices/{device_id}/contacts",
                headers=get_api_headers(),
                timeout=5
            )
            if contact_response.status_code == 200:
                contacts = contact_response.json()
                if chat_id in contacts:
                    contact_info = contacts[chat_id]
                    if contact_info.get('FullName'):
                        chat_name = contact_info['FullName']
                    elif contact_info.get('FirstName'):
                        chat_name = contact_info['FirstName']
        else:  # grupo
            groups_response = requests.get(
                f"{Config.API_URL}/whatsapp/devices/{device_id}/groups",
                headers=get_api_headers(),
                timeout=5
            )
            if groups_response.status_code == 200:
                groups = groups_response.json()
                for group in groups:
                    if group.get('JID') == chat_id:
                        chat_name = group.get('Name', chat_id)
                        break
    except:
        # Em caso de erro, manter o ID do chat como nome
        pass
    
    return render_template(
        'whatsapp/messages.html', 
        messages=messages, 
        device=device, 
        device_id=device_id,
        chat_type=chat_type,
        chat_id=chat_id,
        chat_name=chat_name,
        filter=filter_param
    )

@whatsapp_bp.route('/devices/<device_id>/tracked', methods=['GET'])
@login_required
def get_tracked_entities(device_id):
    # Obter lista de entidades rastreadas
    tracked_entities = []
    try:
        response = requests.get(
            f"{Config.API_URL}/whatsapp/devices/{device_id}/tracked",
            headers=get_api_headers(),
            timeout=10
        )
        
        if response.status_code == 200:
            tracked_entities = response.json()
        else:
            error_detail = "Erro desconhecido"
            try:
                error_data = response.json()
                error_detail = error_data.get('detail', str(response.status_code))
            except:
                error_detail = f"Erro {response.status_code}"
            
            flash(f"Erro ao obter entidades rastreadas: {error_detail}", "danger")
    except requests.exceptions.RequestException as e:
        flash(f"Erro ao obter entidades rastreadas: {e}", "danger")
    
    # Obter dispositivo
    device = None
    try:
        device_response = requests.get(
            f"{Config.API_URL}/whatsapp/devices/{device_id}",
            headers=get_api_headers(),
            timeout=5
        )
        if device_response.status_code == 200:
            device = device_response.json()
    except:
        pass
    
    # Obter lista de contatos e grupos para seleção
    contacts = {}
    groups = []
    
    try:
        contacts_response = requests.get(
            f"{Config.API_URL}/whatsapp/devices/{device_id}/contacts",
            headers=get_api_headers(),
            timeout=10
        )
        if contacts_response.status_code == 200:
            contacts = contacts_response.json()
            
        groups_response = requests.get(
            f"{Config.API_URL}/whatsapp/devices/{device_id}/groups",
            headers=get_api_headers(),
            timeout=10
        )
        if groups_response.status_code == 200:
            groups = groups_response.json()
    except:
        pass
    
    return render_template(
        'whatsapp/tracked_entities.html',
        tracked_entities=tracked_entities,
        device=device,
        device_id=device_id,
        contacts=contacts,
        groups=groups
    )

@whatsapp_bp.route('/devices/<device_id>/tracked', methods=['POST'])
@login_required
def set_tracked_entity(device_id):
    # Adicionar uma nova entidade para rastreamento
    jid = request.form.get('jid')
    is_tracked = request.form.get('is_tracked', 'true').lower() == 'true'
    track_media = request.form.get('track_media', 'true').lower() == 'true'
    allowed_media_types = request.form.getlist('allowed_media_types')
    
    if not jid:
        flash("ID de contato/grupo não fornecido", "danger")
        return redirect(url_for('whatsapp.get_tracked_entities', device_id=device_id))
    
    # Se nenhum tipo de mídia foi selecionado, usar todos
    if not allowed_media_types:
        allowed_media_types = ["image", "audio", "video", "document"]
    
    data = {
        "jid": jid,
        "is_tracked": is_tracked,
        "track_media": track_media,
        "allowed_media_types": allowed_media_types
    }
    
    try:
        response = requests.post(
            f"{Config.API_URL}/whatsapp/devices/{device_id}/tracked",
            headers=get_api_headers(),
            json=data,
            timeout=10
        )
        
        if response.status_code == 200:
            flash("Configuração de rastreamento atualizada com sucesso!", "success")
        else:
            error_detail = "Erro desconhecido"
            try:
                error_data = response.json()
                error_detail = error_data.get('detail', str(response.status_code))
            except:
                error_detail = f"Erro {response.status_code}"
            
            flash(f"Erro ao configurar rastreamento: {error_detail}", "danger")
    except requests.exceptions.RequestException as e:
        flash(f"Erro ao configurar rastreamento: {e}", "danger")
    
    return redirect(url_for('whatsapp.get_tracked_entities', device_id=device_id))

@whatsapp_bp.route('/devices/<device_id>/tracked/<jid>', methods=['DELETE'])
@login_required
def delete_tracked_entity(device_id, jid):
    # Remover uma entidade do rastreamento
    try:
        response = requests.delete(
            f"{Config.API_URL}/whatsapp/devices/{device_id}/tracked/{jid}",
            headers=get_api_headers(),
            timeout=10
        )
        
        if response.status_code == 200:
            return jsonify({"status": "success", "message": "Entidade removida do rastreamento com sucesso"})
        else:
            error_detail = "Erro desconhecido"
            try:
                error_data = response.json()
                error_detail = error_data.get('detail', str(response.status_code))
            except:
                error_detail = f"Erro {response.status_code}"
            
            return jsonify({"status": "error", "message": f"Erro ao remover entidade: {error_detail}"})
    except requests.exceptions.RequestException as e:
        return jsonify({"status": "error", "message": f"Erro ao remover entidade: {e}"})
    
# @app.template_filter('to_json')
# def to_json_filter(value):
#     import json
#     return json.dumps(value)


    
@whatsapp_bp.route('/devices/<device_id>/group/participants')
@login_required
def get_group_participants(device_id):
    """Obtém a lista de participantes de um grupo para exibição no modal."""
    group_id = request.args.get('group_id')
    
    if not group_id:
        return jsonify({"error": "ID do grupo não fornecido"}), 400
    
    try:
        # Buscar grupos
        response = requests.get(
            f"{Config.API_URL}/whatsapp/devices/{device_id}/groups",
            headers=get_api_headers(),
            timeout=10
        )
        
        if response.status_code == 200:
            groups = response.json()
            
            # Encontrar o grupo correto
            group = None
            for g in groups:
                if g.get('JID') == group_id:
                    group = g
                    break
            
            if group and 'Participants' in group:
                return jsonify({"participants": group['Participants']})
            else:
                return jsonify({"participants": []})
        else:
            return jsonify({"error": "Erro ao obter informações do grupo"}), response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500