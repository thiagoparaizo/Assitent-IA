# admin/views/knowledge.py
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
import requests
import os
import uuid

from admin.config import Config

knowledge_bp = Blueprint('knowledge', __name__, url_prefix='/knowledge')

def get_api_headers():
    headers = {
        'Content-Type': 'application/json',
    }
    
    # Add token if user is authenticated
    if hasattr(current_user, 'token') and current_user.token:
        headers['Authorization'] = f'Bearer {current_user.token}'
    
    # Add tenant ID if available
    if hasattr(current_user, 'tenant_id') and current_user.tenant_id:
        headers['X-Tenant-ID'] = str(current_user.tenant_id)
    
    return headers

def get_multipart_headers():
    headers = get_api_headers()
    # Remover Content-Type para permitir que o requests defina o boundary correto
    if 'Content-Type' in headers:
        del headers['Content-Type']
    return headers

@knowledge_bp.route('/')
@login_required
def index():
    # Obter categoria selecionada da query string
    selected_category = request.args.get('category')
    
    # Obter lista de documentos via API
    documents = []
    categories = []
    total_documents = 0
    
    try:
        # Obter categorias
        response = requests.get(
            f"{Config.API_URL}/knowledge/categories",
            headers=get_api_headers(),
            timeout=5
        )
        if response.status_code == 200:
            categories = response.json().get('categories', [])
            
        # Obter documentos
        url = f"{Config.API_URL}/knowledge/documents"
        if selected_category:
            url += f"?category={selected_category}"
            
        response = requests.get(
            url,
            headers=get_api_headers(),
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            documents = data.get('documents', [])
            total_documents = data.get('total', 0)
    except requests.exceptions.RequestException as e:
        flash(f"Erro ao obter dados: {e}", "danger")
    
    # Calcular total de documentos em todas as categorias se necessário
    if not total_documents and categories:
        total_documents = sum(category.get('document_count', 0) for category in categories)
    
    return render_template(
        'knowledge/index.html', 
        documents=documents,
        categories=categories,
        selected_category=selected_category,
        total_documents=total_documents
    )

@knowledge_bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        category = request.form.get('category')
        description = request.form.get('description', '')
        
        # Verificar se os arquivos foram enviados
        if 'files' not in request.files:
            flash('Nenhum arquivo enviado', 'danger')
            return redirect(request.url)
        
        files = request.files.getlist('files')
        
        # Verificar se há arquivos selecionados
        if not files or files[0].filename == '':
            flash('Nenhum arquivo selecionado', 'danger')
            return redirect(request.url)
        
        # Enviar arquivos para a API
        try:
            # Preparar dados para upload multipart
            files_data = []
            for file in files:
                files_data.append(('files', (file.filename, file.read(), file.content_type)))
            
            # Adicionar outros campos do formulário
            form_data = {
                'category': category,
                'description': description,
                'tenant_id': str(current_user.tenant_id) if current_user.tenant_id else '1'
            }
            
            # Enviar para a API
            response = requests.post(
                f"{Config.API_URL}/knowledge/upload",
                headers=get_multipart_headers(),
                files=files_data,
                data=form_data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                flash(f"Upload concluído com sucesso! {result.get('message', '')}", "success")
                return redirect(url_for('knowledge.index'))
            else:
                error_detail = "Erro desconhecido"
                try:
                    error_data = response.json()
                    error_detail = error_data.get('detail', str(response.status_code))
                except:
                    error_detail = f"Erro {response.status_code}"
                
                flash(f"Erro ao fazer upload: {error_detail}", "danger")
                
        except requests.exceptions.RequestException as e:
            flash(f"Erro ao enviar arquivos: {e}", "danger")
        
    # Obter categorias
    categories = []
    try:
        response = requests.get(
            f"{Config.API_URL}/knowledge/categories",
            headers=get_api_headers(),
            timeout=5
        )
        if response.status_code == 200:
            categories = response.json()['categories']
    except requests.exceptions.RequestException:
        categories = [
            {"id": "general", "name": "Geral"},
            {"id": "agendamento", "name": "Agendamento"},
            {"id": "procedimentos", "name": "Procedimentos"},
            {"id": "financeiro", "name": "Financeiro"}
        ]
    
    return render_template('knowledge/upload.html', categories=categories)

@knowledge_bp.route('/categories', methods=['GET', 'POST'])
@login_required
def categories():
    if request.method == 'POST':
        category_id = request.form.get('id', uuid.uuid4().hex)
        name = request.form.get('name')
        description = request.form.get('description', '')
        
        # Enviar para API
        try:
            response = requests.post(
                f"{Config.API_URL}/knowledge/categories",
                headers=get_api_headers(),
                json={
                    'id': category_id,
                    'name': name,
                    'description': description
                },
                timeout=5
            )
            
            if response.status_code == 200:
                flash("Categoria criada com sucesso!", "success")
            else:
                error_detail = "Erro desconhecido"
                try:
                    error_data = response.json()
                    error_detail = error_data.get('detail', str(response.status_code))
                except:
                    error_detail = f"Erro {response.status_code}"
                
                flash(f"Erro ao criar categoria: {error_detail}", "danger")
                
        except requests.exceptions.RequestException as e:
            flash(f"Erro ao criar categoria: {e}", "danger")
    
    # Obter categorias
    categories = []
    try:
        response = requests.get(
            f"{Config.API_URL}/knowledge/categories",
            headers=get_api_headers(),
            timeout=5
        )
        if response.status_code == 200:
            categories = response.json()['categories']
    except requests.exceptions.RequestException as e:
        flash(f"Erro ao obter categorias: {e}", "danger")
    
    return render_template('knowledge/categories.html', categories=categories)

@knowledge_bp.route('/categories/<category_id>/delete', methods=['POST'])
@login_required
def delete_category(category_id):
    # Enviar para API
    try:
        response = requests.delete(
            f"{Config.API_URL}/knowledge/categories/{category_id}",
            headers=get_api_headers(),
            timeout=5
        )
        
        if response.status_code == 200:
            flash("Categoria removida com sucesso!", "success")
        else:
            error_detail = "Erro desconhecido"
            try:
                error_data = response.json()
                error_detail = error_data.get('detail', str(response.status_code))
            except:
                error_detail = f"Erro {response.status_code}"
            
            flash(f"Erro ao remover categoria: {error_detail}", "danger")
            
    except requests.exceptions.RequestException as e:
        flash(f"Erro ao remover categoria: {e}", "danger")
        
    return redirect(url_for('knowledge.categories'))

@knowledge_bp.route('/document/<document_id>/delete', methods=['POST'])
@login_required
def delete_document(document_id):
    """Exclui um documento da base de conhecimento."""
    try:
        response = requests.delete(
            f"{Config.API_URL}/knowledge/documents/{document_id}",
            headers=get_api_headers(),
            timeout=5
        )
        
        if response.status_code == 200:
            flash("Documento excluído com sucesso!", "success")
        else:
            error_detail = "Erro desconhecido"
            try:
                error_data = response.json()
                error_detail = error_data.get('detail', str(response.status_code))
            except:
                error_detail = f"Erro {response.status_code}"
            
            flash(f"Erro ao excluir documento: {error_detail}", "danger")
    except requests.exceptions.RequestException as e:
        flash(f"Erro ao excluir documento: {e}", "danger")
        
    return redirect(url_for('knowledge.index'))