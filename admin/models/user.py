# admin/models/user.py
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

class User(UserMixin):
    """
    Modelo de usuário para a interface administrativa.
    Como estamos usando a API para autenticação, este é um modelo simplificado.
    """
    
    def __init__(self, id, email, tenant_id=None, is_active_flag=True, is_superuser=False):
        self.id = id
        self.email = email
        self.tenant_id = tenant_id
        self._is_active = is_active_flag  # Renomeado para evitar conflito
        self.is_superuser = is_superuser
        self._token = None
    
    @property
    def is_active(self):
        # Sobrescreve o método is_active do UserMixin
        return self._is_active
    
    @property
    def token(self):
        return self._token
    
    @token.setter
    def token(self, value):
        self._token = value
    
    @classmethod
    def get(cls, user_id):
        """
        Método para carregar um usuário pelo ID.
        Na implementação real, buscaria no banco de dados ou API.
        """
        # Implementação simplificada para demonstração
        from admin.models.user_store import user_store
        return user_store.get(user_id)