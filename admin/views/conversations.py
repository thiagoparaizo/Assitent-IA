# admin/views/conversations.py
from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required

conversations_bp = Blueprint('conversations', __name__, url_prefix='/conversations')

@conversations_bp.route('/')
@login_required
def index():
    # Implementação básica
    return render_template('conversations/index.html')

@conversations_bp.route('/<conversation_id>')
@login_required
def view(conversation_id):
    # Implementação básica
    return render_template('conversations/view.html', conversation_id=conversation_id)