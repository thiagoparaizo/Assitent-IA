# admin/models/user.py
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

class User(UserMixin):
    """
    Modelo de usuário para a interface administrativa.
    Como estamos usando a API para autenticação, este é um modelo simplificado.
    """
    
    def __init__(self, id, email, tenant_id=None, is_active=True, is_superuser=False, token=None):
        self.id = str(id)  # Garanta que o ID seja sempre string
        self.email = email
        self.tenant_id = tenant_id
        self._is_active = is_active
        self.is_superuser = is_superuser
        self.token = token

    def get_id(self):
        return self.id  # Flask-Login requer este método


    @property
    def is_active(self):
        return self._is_active

    @is_active.setter
    def is_active(self, value):
        self._is_active = value
    @property
    def is_authenticated(self):
        return True  # Sobrescreva explicitamente
    
    @property
    def is_active(self):
        # Sobrescreve o método is_active do UserMixin
        return self._is_active
    
    @classmethod
    def get(cls, user_id):
        """
        Método para carregar um usuário pelo ID.
        Na implementação real, buscaria no banco de dados ou API.
        """
        # Implementação simplificada para demonstração
        from admin.models.user_store import user_store
        return user_store.get(str(user_id))