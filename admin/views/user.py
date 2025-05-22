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


@user_bp.route('/')
@login_required
def index():
    """List all users."""
    users = []
    tenants = []
    
    try:
        # Get users
        params = {}
        if not current_user.is_superuser and current_user.tenant_id:
            params['tenant_id'] = current_user.tenant_id
            
        response = requests.get(
            f"{Config.API_URL}/user/",
            headers=get_api_headers(),
            params=params,
            timeout=5
        )
        
        if response.status_code == 200:
            users = response.json()
        else:
            flash(f"Erro ao carregar usuários: {response.status_code}", "danger")
        
        # Get tenants for display (if superuser)
        if current_user.is_superuser:
            tenants_response = requests.get(
                f"{Config.API_URL}/tenants/",
                headers=get_api_headers(),
                timeout=5
            )
            
            if tenants_response.status_code == 200:
                tenants = tenants_response.json()
                
                # Create a mapping for tenant names
                tenant_map = {tenant['id']: tenant['name'] for tenant in tenants}
                
                # Add tenant names to users
                for user in users:
                    user['tenant_name'] = tenant_map.get(user.get('tenant_id'), 'Sem tenant')
            
    except requests.exceptions.RequestException as e:
        flash(f"Erro ao conectar com a API: {str(e)}", "danger")
    
    return render_template('user/index.html', users=users, tenants=tenants)

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
        
@user_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """Create a new user."""
    # Check if user is superuser
    if not current_user.is_superuser:
        flash('Você não tem permissão para criar usuários.', 'danger')
        return redirect(url_for('user.index'))
    
    tenants = []
    preselected_tenant_id = request.args.get('tenant_id', type=int)  # Pegar tenant da URL
    
    # Get tenants for the form
    try:
        tenants_response = requests.get(
            f"{Config.API_URL}/tenants/",
            headers=get_api_headers(),
            timeout=5
        )
        
        if tenants_response.status_code == 200:
            tenants = tenants_response.json()
    except requests.exceptions.RequestException as e:
        flash(f"Erro ao carregar tenants: {str(e)}", "warning")
    
    if request.method == 'POST':
        # Get form data
        user_data = {
            'email': request.form.get('email'),
            'password': request.form.get('password'),
            'full_name': request.form.get('full_name'),
            'tenant_id': int(request.form.get('tenant_id')) if request.form.get('tenant_id') else None,
            'is_superuser': 'is_superuser' in request.form
        }
        
        # Validate form
        if not user_data['email'] or not user_data['password']:
            flash('Email e senha são obrigatórios.', 'danger')
            return render_template('user/create.html', tenants=tenants, preselected_tenant_id=preselected_tenant_id)
        
        if request.form.get('password') != request.form.get('confirm_password'):
            flash('Senha e confirmação de senha não coincidem.', 'danger')
            return render_template('user/create.html', tenants=tenants, preselected_tenant_id=preselected_tenant_id)
        
        try:
            # Call API to create user
            response = requests.post(
                f"{Config.API_URL}/user/",
                headers=get_api_headers(),
                json=user_data,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                flash('Usuário criado com sucesso!', 'success')
                
                # Redirecionar para o tenant se veio de lá
                if preselected_tenant_id:
                    return redirect(url_for('tenants.view', tenant_id=preselected_tenant_id))
                else:
                    return redirect(url_for('user.index'))
            else:
                error_detail = "Erro desconhecido"
                try:
                    error_data = response.json()
                    error_detail = error_data.get('detail', str(response.status_code))
                except:
                    error_detail = f"Erro {response.status_code}"
                
                flash(f"Erro ao criar usuário: {error_detail}", "danger")
        except requests.exceptions.RequestException as e:
            flash(f"Erro ao conectar com a API: {str(e)}", "danger")
    
    return render_template('user/create.html', tenants=tenants, preselected_tenant_id=preselected_tenant_id)

@user_bp.route('/<user_id>')
@login_required
def view(user_id):
    """View user details."""
    user = None
    tenant = None
    
    try:
        # Get user details
        response = requests.get(
            f"{Config.API_URL}/user/{user_id}",
            headers=get_api_headers(),
            timeout=5
        )
        
        if response.status_code == 200:
            user = response.json()
            
            # Get tenant details if user has one
            if user.get('tenant_id'):
                try:
                    tenant_response = requests.get(
                        f"{Config.API_URL}/tenants/{user['tenant_id']}",
                        headers=get_api_headers(),
                        timeout=3
                    )
                    if tenant_response.status_code == 200:
                        tenant = tenant_response.json()
                except:
                    pass
        else:
            flash(f"Erro ao carregar usuário: {response.status_code}", "danger")
            return redirect(url_for('user.index'))
    except requests.exceptions.RequestException as e:
        flash(f"Erro ao conectar com a API: {str(e)}", "danger")
        return redirect(url_for('user.index'))
    
    if not user:
        flash('Usuário não encontrado.', 'danger')
        return redirect(url_for('user.index'))
    
    return render_template('user/view.html', user=user, tenant=tenant)

@user_bp.route('/<user_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(user_id):
    """Edit user details."""
    user = None
    tenants = []
    
    # Get user details
    try:
        response = requests.get(
            f"{Config.API_URL}/user/{user_id}",
            headers=get_api_headers(),
            timeout=5
        )
        
        if response.status_code == 200:
            user = response.json()
        else:
            flash(f"Erro ao carregar usuário: {response.status_code}", "danger")
            return redirect(url_for('user.index'))
    except requests.exceptions.RequestException as e:
        flash(f"Erro ao conectar com a API: {str(e)}", "danger")
        return redirect(url_for('user.index'))
    
    if not user:
        flash('Usuário não encontrado.', 'danger')
        return redirect(url_for('user.index'))
    
    # Check permissions
    if not current_user.is_superuser and current_user.id != user['id']:
        flash('Você não tem permissão para editar este usuário.', 'danger')
        return redirect(url_for('user.index'))
    
    # Get tenants for the form (if superuser)
    if current_user.is_superuser:
        try:
            tenants_response = requests.get(
                f"{Config.API_URL}/tenants/",
                headers=get_api_headers(),
                timeout=5
            )
            
            if tenants_response.status_code == 200:
                tenants = tenants_response.json()
        except requests.exceptions.RequestException as e:
            flash(f"Erro ao carregar tenants: {str(e)}", "warning")
    
    if request.method == 'POST':
        # Get form data
        user_data = {
            'email': request.form.get('email'),
            'full_name': request.form.get('full_name'),
        }
        
        # Only superusers can change these fields
        if current_user.is_superuser:
            if request.form.get('tenant_id'):
                user_data['tenant_id'] = int(request.form.get('tenant_id'))
            user_data['is_superuser'] = 'is_superuser' in request.form
            user_data['is_active'] = 'is_active' in request.form
        
        # Handle password change
        new_password = request.form.get('new_password')
        if new_password:
            if new_password != request.form.get('confirm_password'):
                flash('Nova senha e confirmação não coincidem.', 'danger')
                return render_template('user/edit.html', user=user, tenants=tenants)
            user_data['password'] = new_password
        
        try:
            # Call API to update user
            response = requests.put(
                f"{Config.API_URL}/user/{user_id}",
                headers=get_api_headers(),
                json=user_data,
                timeout=10
            )
            
            if response.status_code == 200:
                flash('Usuário atualizado com sucesso!', 'success')
                return redirect(url_for('user.view', user_id=user_id))
            else:
                error_detail = "Erro desconhecido"
                try:
                    error_data = response.json()
                    error_detail = error_data.get('detail', str(response.status_code))
                except:
                    error_detail = f"Erro {response.status_code}"
                
                flash(f"Erro ao atualizar usuário: {error_detail}", "danger")
        except requests.exceptions.RequestException as e:
            flash(f"Erro ao conectar com a API: {str(e)}", "danger")
    
    return render_template('user/edit.html', user=user, tenants=tenants)

@user_bp.route('/<user_id>/delete', methods=['POST'])
@login_required
def delete(user_id):
    """Delete a user."""
    # Check if user is superuser
    if not current_user.is_superuser:
        flash('Você não tem permissão para excluir usuários.', 'danger')
        return redirect(url_for('user.index'))
    
    try:
        # Call API to delete user
        response = requests.delete(
            f"{Config.API_URL}/user/{user_id}",
            headers=get_api_headers(),
            timeout=10
        )
        
        if response.status_code == 200:
            flash('Usuário excluído com sucesso!', 'success')
        else:
            error_detail = "Erro desconhecido"
            try:
                error_data = response.json()
                error_detail = error_data.get('detail', str(response.status_code))
            except:
                error_detail = f"Erro {response.status_code}"
            
            flash(f"Erro ao excluir usuário: {error_detail}", "danger")
    except requests.exceptions.RequestException as e:
        flash(f"Erro ao conectar com a API: {str(e)}", "danger")
    
    return redirect(url_for('user.index'))

@user_bp.route('/<user_id>/activate', methods=['POST'])
@login_required
def activate(user_id):
    """Activate a user."""
    if not current_user.is_superuser:
        flash('Você não tem permissão para ativar usuários.', 'danger')
        return redirect(url_for('user.index'))
    
    try:
        response = requests.put(
            f"{Config.API_URL}/user/{user_id}/activate",
            headers=get_api_headers(),
            timeout=10
        )
        
        if response.status_code == 200:
            flash('Usuário ativado com sucesso!', 'success')
        else:
            flash(f"Erro ao ativar usuário: {response.status_code}", "danger")
    except requests.exceptions.RequestException as e:
        flash(f"Erro ao conectar com a API: {str(e)}", "danger")
    
    return redirect(url_for('user.view', user_id=user_id))

@user_bp.route('/<user_id>/deactivate', methods=['POST'])
@login_required
def deactivate(user_id):
    """Deactivate a user."""
    if not current_user.is_superuser:
        flash('Você não tem permissão para desativar usuários.', 'danger')
        return redirect(url_for('user.index'))
    
    try:
        response = requests.put(
            f"{Config.API_URL}/user/{user_id}/deactivate",
            headers=get_api_headers(),
            timeout=10
        )
        
        if response.status_code == 200:
            flash('Usuário desativado com sucesso!', 'success')
        else:
            flash(f"Erro ao desativar usuário: {response.status_code}", "danger")
    except requests.exceptions.RequestException as e:
        flash(f"Erro ao conectar com a API: {str(e)}", "danger")
    
    return redirect(url_for('user.view', user_id=user_id))

@user_bp.route('/<user_id>/reset-password', methods=['POST'])
@login_required
def reset_password(user_id):
    """Reset user password."""
    if not current_user.is_superuser:
        flash('Você não tem permissão para redefinir senhas.', 'danger')
        return redirect(url_for('user.index'))
    
    new_password = request.form.get('new_password')
    if not new_password:
        flash('Nova senha é obrigatória.', 'danger')
        return redirect(url_for('user.view', user_id=user_id))
    
    try:
        response = requests.post(
            f"{Config.API_URL}/user/{user_id}/reset-password",
            headers=get_api_headers(),
            json={"new_password": new_password},
            timeout=10
        )
        
        if response.status_code == 200:
            flash('Senha redefinida com sucesso!', 'success')
        else:
            flash(f"Erro ao redefinir senha: {response.status_code}", "danger")
    except requests.exceptions.RequestException as e:
        flash(f"Erro ao conectar com a API: {str(e)}", "danger")
    
    return redirect(url_for('user.view', user_id=user_id))