# admin/app.py
from flask import Flask, render_template, redirect, url_for, flash, request, session
from flask_login import LoginManager, login_required, login_user, logout_user, current_user
import os

from admin.config import Config
from admin.views.auth import auth_bp
from admin.views.dashboard import dashboard_bp
from admin.views.agents import agents_bp
from admin.views.knowledge import knowledge_bp
from admin.views.tenants import tenants_bp
from admin.views.whatsapp import whatsapp_bp
from admin.views.conversations import conversations_bp
from admin.models.user import User

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
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
    
    # Configurar contexto global
    @app.context_processor
    def inject_user():
        return dict(user=current_user)
    
    @login_manager.user_loader
    def load_user(user_id):
        # Implementar carregamento de usuário
        return User.get(user_id)
    
    @app.route('/')
    def index():
        return redirect(url_for('dashboard.index'))
    
    # Criar pasta de uploads se não existir
    uploads_dir = app.config['UPLOAD_FOLDER']
    if not os.path.exists(uploads_dir):
        os.makedirs(uploads_dir)
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)