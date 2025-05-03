# admin/models/user_store.py
from admin.models.user import User

class UserStore:
    """
    Armazenamento simplificado de usuários para demonstração.
    Em produção, usaria banco de dados.
    """
    
    def __init__(self):
        self.users = {}
        
        
        # # Criar alguns usuários de exemplo
        # self.add_user(User(1, 'admin@example.com', None, True, True))
        # self.add_user(User(2, 'tenant1@example.com', 1, True, False))
        # self.add_user(User(3, 'tenant2@example.com', 2, True, False))
    
    def add_user(self, user):
        self.users[user.id] = user  # Armazene pelo ID como string

    def get(self, user_id):
        return self.users.get(str(user_id))  # Busque como string
    
    def get_by_email(self, email):
        return self.emails.get(email)
    
    def clear(self):
        self.users.clear()
        self.emails.clear()

# Instância global
user_store = UserStore()