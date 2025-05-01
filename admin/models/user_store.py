# admin/models/user_store.py
from admin.models.user import User

class UserStore:
    """
    Armazenamento simplificado de usuários para demonstração.
    Em produção, usaria banco de dados.
    """
    
    def __init__(self):
        self.users = {}
        self.emails = {}
        
        # Criar alguns usuários de exemplo
        self.add_user(User(1, 'admin@example.com', None, True, True))
        self.add_user(User(2, 'tenant1@example.com', 1, True, False))
        self.add_user(User(3, 'tenant2@example.com', 2, True, False))
    
    def add_user(self, user):
        self.users[user.id] = user
        self.emails[user.email] = user
    
    def get(self, user_id):
        return self.users.get(int(user_id))
    
    def get_by_email(self, email):
        return self.emails.get(email)

# Instância global
user_store = UserStore()