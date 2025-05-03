# admin/views/auth.py
import time
from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
import requests
import json

from admin.models.user import User
from admin.models.user_store import user_store
from admin.config import Config

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if hasattr(current_user, 'is_authenticated') and current_user.is_authenticated == True:
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = 'remember' in request.form
        
        if not email or not password:
            flash('Por favor, preencha todos os campos.', 'danger')
            return render_template('auth/login.html')
        
        # Authenticate using the API
        try:
            # Call the authentication API
            response = requests.post(
                f"{Config.API_URL}/auth/login",
                data={
                    "username": email,  # OAuth2 uses username field
                    "password": password
                },
                timeout=10
            )
            
            if response.status_code == 200:
                token_data = response.json()
                access_token = token_data.get("access_token")
                
                # Get user info with this token
                user_response = requests.get(
                    f"{Config.API_URL}/auth/me",
                    headers={
                        "Authorization": f"Bearer {access_token}"
                    },
                    timeout=10
                )
                
                if user_response.status_code == 200:
                    user_data = user_response.json()
                    
                    user = User(
                        id=user_data['id'],
                        email=user_data['email'],
                        tenant_id=user_data.get('tenant_id'),
                        is_active=user_data.get('is_active', True),
                        is_superuser=user_data.get('is_superuser', False),
                        token=access_token
                    )
                    
                    print(f"Usuário criado: {user.__dict__}")  # Log
                    user_store.add_user(user)
                    print(f"User Store após adição: {user_store.users}")  # Log
                    
                    login_user(user, remember=remember)
                    print(f"Current User após login: {current_user.__dict__}")  # Log
                    
                    # Commit da sessão
                    session.permanent = True
                    session['user_id'] = user.id
                    session['auth_token'] = access_token
                    session['last_token_verify'] = time.time()
                    print(f"Sessão após login: {dict(session)}")  # Log
                    
                    # Redirect to the next page or dashboard
                    next_page = request.args.get('next')
                    if not next_page or not next_page.startswith('/'):
                        next_page = url_for('dashboard.index')
                    
                    flash(f"Bem-vindo, {user.email}!", "success")
                    return redirect(next_page or url_for('dashboard.index'))
                else:
                    flash('Erro ao obter informações do usuário.', 'danger')
            else:
                # Handle authentication error
                flash('Email ou senha inválidos.', 'danger')
        except requests.exceptions.RequestException as e:
            flash(f'Erro de conexão com o servidor: {str(e)}', 'danger')
    
    return render_template('auth/login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Você saiu do sistema.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/profile', methods=['GET', 'POST'])
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
                return render_template('auth/profile.html')
            
            # Try to change password via API
            try:
                response = requests.post(
                    f"{Config.API_URL}/auth/change-password",
                    headers={
                        "Authorization": f"Bearer {current_user.token}",
                        "Content-Type": "application/json"
                    },
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
        
    return render_template('auth/profile.html')