# admin/app.py
from datetime import datetime
import time
from flask import Flask, render_template, redirect, url_for, flash, request, session
from flask_login import LoginManager, login_required, current_user, login_user, logout_user
import os
import requests

from admin.config import Config
from admin.views.auth import auth_bp
from admin.views.dashboard import dashboard_bp
from admin.views.agents import agents_bp
from admin.views.knowledge import knowledge_bp
from admin.views.tenants import tenants_bp
from admin.views.whatsapp import whatsapp_bp
from admin.views.conversations import conversations_bp
from admin.views.webhooks import webhooks_bp
from admin.views.user import user_bp
from admin.models.user import User
from admin.models.user_store import user_store


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Configuração crítica que estava faltando
    app.config.update(
        SECRET_KEY=Config.SECRET_KEY,  # Deve ser igual ao da API
        SESSION_COOKIE_NAME='webapp_session',
        PERMANENT_SESSION_LIFETIME=3600  # 1 hora
    )
    
    # Configurar Login Manager
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Por favor, faça login para acessar esta página.'
    login_manager.login_message_category = 'warning'
    
    # Registrar blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(agents_bp)
    app.register_blueprint(knowledge_bp)
    app.register_blueprint(tenants_bp)
    app.register_blueprint(whatsapp_bp)
    app.register_blueprint(conversations_bp)
    app.register_blueprint(webhooks_bp)
    app.register_blueprint(user_bp)
    
    # Configurar contexto global
    @app.context_processor
    def inject_user():
        return dict(user=current_user)
    
    @login_manager.user_loader
    def load_user(user_id):
        return user_store.get(user_id)
    
    @app.route('/')
    def index():
        return redirect(url_for('dashboard.index'))
    
    # Criar pasta de uploads se não existir
    uploads_dir = app.config['UPLOAD_FOLDER']
    if not os.path.exists(uploads_dir):
        os.makedirs(uploads_dir)
    
    
    @app.template_filter('datetime')
    def format_datetime(value, format='%d/%m/%Y %H:%M'):
        if value is None:
            return ""
        if isinstance(value, (int, float)):
            value = datetime.fromtimestamp(value)
        try:
            return value.strftime(format)
        except:
            return str(value)
        
    @app.template_filter('sort_by_name')
    def sort_by_name(contacts_dict):
        # Converter para lista de tuplas (jid, contact)
        contacts_list = list(contacts_dict.items())
        
        # Definir uma função para obter o nome de exibição
        def get_display_name(item):
            jid, contact = item
            return contact.get("FullName") or contact.get("FirstName") or contact.get("BusinessName") or jid
        
        # Ordenar a lista
        return sorted(contacts_list, key=get_display_name)
    
    @app.before_request
    def check_auth_and_verify_token():
        # Public routes that don't require authentication
        public_routes = ['static', 'auth.login']
        
        # If endpoint is public, allow access
        if request.endpoint and any(request.endpoint.startswith(route) for route in public_routes):
            return
            
        # If user is not authenticated, redirect to login
        if not hasattr(current_user, 'is_authenticated') or current_user.is_authenticated == False:
            print("User is not authenticated")
            # Only redirect if this is not the login page itself
            if request.endpoint != 'auth.login':
                print("User is not authenticated and not on login page")
                return login_manager.unauthorized()
        
        # If user is authenticated but token may be expired, verify it
        elif current_user.is_authenticated and hasattr(current_user, 'token'):
            print("User is authenticated")
            # Only verify token periodically or for important operations
            # to avoid too many API calls
            should_verify = False
            
            # Check session data to determine if verification is needed
            last_verify = session.get('last_token_verify', 0)
            now = time.time()
            
            # Verify every 5 minutes
            if now - last_verify > 300:  # 5 minutes in seconds
                should_verify = True
                session['last_token_verify'] = now
            
            if should_verify:
                try:
                    # Test token against API
                    response = requests.post(
                        f"{Config.API_URL}/auth/test-token",
                        headers={"Authorization": f"Bearer {current_user.token}"},
                        timeout=5
                    )
                    
                    if response.status_code != 200:
                        # Token is invalid, log the user out
                        logout_user()
                        flash('Sua sessão expirou. Por favor, faça login novamente.', 'warning')
                        return redirect(url_for('auth.login'))
                except requests.exceptions.RequestException as e:
                    # Tratar erros de rede/conexão
                    print(f"Erro ao verificar token: {e}")
                    # On error, continue but don't update last_verify
                    session['last_token_verify'] = last_verify
                except Exception as e:
                    # Tratar outros erros inesperados
                    print(f"Erro inesperado ao verificar token: {e}")
                    session['last_token_verify'] = last_verify
    
    return app  

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)