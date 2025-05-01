# admin/views/tenants.py
from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required

# Aqui está o problema - você precisa definir o blueprint
tenants_bp = Blueprint('tenants', __name__, url_prefix='/tenants')

@tenants_bp.route('/')
@login_required
def index():
    # Implementação básica por enquanto
    return render_template('tenants/index.html')