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

@whatsapp_bp.route('/devices/<device_id>/disconnect', methods=['POST'])
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