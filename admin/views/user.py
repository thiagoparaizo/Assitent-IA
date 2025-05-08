# admin/views/user.py
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
import requests

from admin.config import Config

user_bp = Blueprint('user', __name__, url_prefix='/user')

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

@user_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        # Get form data
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        # Validate passwords
        if current_password and new_password:
            if new_password != confirm_password:
                flash('Nova senha e confirmação não correspondem.', 'danger')
                return render_template('user/profile.html')
            
            # Try to change password via API
            try:
                response = requests.post(
                    f"{Config.API_URL}/auth/change-password",
                    headers=get_api_headers(),
                    json={
                        "current_password": current_password,
                        "new_password": new_password
                    },
                    timeout=10
                )
                
                if response.status_code == 200:
                    flash('Senha alterada com sucesso!', 'success')
                else:
                    flash('Erro ao alterar senha. Verifique se a senha atual está correta.', 'danger')
            except requests.exceptions.RequestException as e:
                flash(f'Erro de conexão com o servidor: {str(e)}', 'danger')

    return render_template('user/profile.html')

@user_bp.route('/<user_id>/profile/data', methods=['GET'])
@login_required
def get_user_profile_data(user_id):
    """
    Obtém os dados de perfil de um usuário para uso via AJAX
    """
    try:
        # Fazer requisição à API para obter o perfil do usuário
        response = requests.get(
            f"{Config.API_URL}/conversations/user/{user_id}/profile",
            headers=get_api_headers(),
            timeout=10
        )
        
        if response.status_code == 200:
            profile_data = response.json()
            return jsonify(profile_data)
        else:
            return jsonify({
                "error": f"Erro ao obter perfil: {response.status_code}",
                "message": response.text
            }), response.status_code
    except Exception as e:
        return jsonify({
            "error": "Erro ao conectar à API",
            "message": str(e)
        }), 500