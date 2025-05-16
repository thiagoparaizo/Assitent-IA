# admin/config.py
import os
from datetime import timedelta

class Config:
    # Configurações básicas
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-here-2025-abc'
    DEBUG = os.environ.get('FLASK_DEBUG') or False
    LOGIN_DISABLED = False
    
    # Configuração do banco de dados
    #SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///app.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Configuração do API
    API_URL = os.environ.get('API_URL') or 'http://localhost:8000/api/v1'
    #API_TOKEN = os.environ.get('API_TOKEN') or ''
    
    # Configuração da sessão
    PERMANENT_SESSION_LIFETIME = timedelta(hours=1)
    
    # Configuração de upload
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB
    
    