# app/api/endpoints/knowledge.py
from datetime import datetime, time
import os
import shutil
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, get_db, get_tenant_id
from app.db.models.user import User
from app.services.rag_faiss import RAGServiceFAISS

from app.core.rag_categories import DEFAULT_CATEGORIES

router = APIRouter()

import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("app.api.endpoints.knowledge")

@router.post("/upload")
async def upload_documents(
    files: List[UploadFile] = File(...),
    tenant_id: int = Form(...),
    category: str = Form(...),
    description: str = Form(None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Upload de documentos para indexação no RAG, com separação por tenant e categoria
    """
    # Verificar permissão
    if not current_user.is_superuser and current_user.tenant_id != int(tenant_id):
        raise HTTPException(status_code=403, detail="Sem permissão para acessar este tenant")
    
    # Criar diretório temporário para armazenar os arquivos
    temp_dir = f"./storage/temp/{tenant_id}_{category}_{int(datetime.now().timestamp())}"
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        # Salvar arquivos no diretório temporário
        file_paths = []
        for file in files:
            file_path = os.path.join(temp_dir, file.filename)
            with open(file_path, "wb") as f:
                f.write(await file.read())
            file_paths.append(file_path)
        
        # Indexar documentos com o RAG
        #rag_service = RAGService(tenant_id=tenant_id)
        #rag_service = SeuProcessador(tenant_id=tenant_id)
        rag_service = RAGServiceFAISS(tenant_id=tenant_id)
        num_chunks = await rag_service.index_documents(temp_dir, category=category)
        
        # Registrar upload no banco de dados (opcional)
        # Você pode criar um modelo Document para rastrear uploads
        
        return JSONResponse(
            content={
                "status": "success",
                "message": f"{len(files)} documentos indexados com sucesso em {num_chunks} chunks",
                "files": [file.filename for file in files],
                "tenant_id": tenant_id,
                "category": category
            },
            status_code=200
        )
    
    except Exception as e:
        print(f"Erro ao indexar documentos: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao indexar documentos: {str(e)}")
    
    finally:
        # Limpar diretório temporário
        shutil.rmtree(temp_dir, ignore_errors=True)


@router.post("/add-text")
async def add_text_knowledge(
    text: str = Form(...),
    title: str = Form(...),
    category: str = Form(...),
    current_user: User = Depends(get_current_active_user),
):
    """
    Adiciona texto diretamente ao knowledge base
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Apenas administradores podem adicionar conhecimento")
    
    # Adicionar metadados
    metadata = {
        "title": title,
        "category": category,
        "added_by": current_user.email,
        "date_added": datetime.now().isoformat()
    }
    
    # Adicionar texto ao RAG
    rag_service = RAGServiceFAISS()
    rag_service.add_text(text, metadata)
    
    return JSONResponse(
        content={
            "status": "success",
            "message": "Texto adicionado com sucesso à base de conhecimento",
            "title": title,
            "category": category
        },
        status_code=200
    )
    
@router.get("/documents")
async def list_documents(
    tenant_id: int = Depends(get_tenant_id),
    category: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
):
    """
    Lista documentos indexados no RAG, com metadados adicionais para agrupamento
    """
    # Verificar permissão
    t = int(tenant_id) if tenant_id else 0
    if not current_user.is_superuser and current_user.tenant_id != t:
        raise HTTPException(status_code=403, detail="Sem permissão para acessar este tenant")
    
    # Inicializar serviço RAG
    rag_service = RAGServiceFAISS(tenant_id=tenant_id)
    
    try:
        # Obter documentos
        documents = await rag_service.list_documents(category=category, skip=skip, limit=limit)
        
        # Agrupar documentos por nome de arquivo para contagem
        filenames = {}
        for doc in documents:
            filename = doc.get("filename", "unknown")
            if filename not in filenames:
                filenames[filename] = 0
            filenames[filename] += 1
        
        # Adicionar contagem de chunks para cada documento
        for doc in documents:
            filename = doc.get("filename", "unknown")
            doc["total_chunks"] = filenames.get(filename, 1)
        
        # Calcular número total de documentos únicos para contagem/paginação
        total_unique_docs = len(filenames)
        
        # Retornar lista de documentos com metadados adicionais
        return {
            "documents": documents,
            "total": len(documents),
            "total_unique": total_unique_docs,
            "skip": skip,
            "limit": limit,
            "unique_files": list(filenames.keys())
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao listar documentos: {str(e)}")
    
# @router.get("/categories")
# async def list_categories(
#     tenant_id: int = Depends(get_tenant_id),
#     current_user: User = Depends(get_current_active_user),
# ):
#     """
#     Lista categorias disponíveis no RAG com contagem correta de documentos únicos
#     """
#     t = int(tenant_id) if tenant_id else 0
#     if not current_user.is_superuser and current_user.tenant_id != t:
#         raise HTTPException(status_code=403, detail="Sem permissão para acessar este tenant")
    
#     # Inicializar serviço RAG
#     rag_service = RAGServiceFAISS(tenant_id=tenant_id)
    
#     try:
#         # Obter categorias
#         categories = await rag_service.list_categories()
        
#         # Obter documentos para contagem correta
#         documents = await rag_service.list_documents()
        
#         # Criar um conjunto de nomes de arquivos únicos por categoria
#         unique_filenames_by_category = {}
        
#         for doc in documents:
#             category = doc.get("category", "general")
#             filename = doc.get("filename", "unknown")
            
#             if category not in unique_filenames_by_category:
#                 unique_filenames_by_category[category] = set()
                
#             unique_filenames_by_category[category].add(filename)
        
#         # Calcular contagem correta por categoria
#         category_counts = {
#             category: len(filenames)
#             for category, filenames in unique_filenames_by_category.items()
#         }
        
#         # Formatar categorias com contagem correta
#         formatted_categories = [
#             {
#                 "id": category,
#                 "name": category.capitalize(),
#                 "document_count": category_counts.get(category, 0)
#             }
#             for category, _ in categories.items()
#         ]
        
#         # Calcular total de documentos únicos para "Todas" as categorias
#         all_filenames = set()
#         for filenames in unique_filenames_by_category.values():
#             all_filenames.update(filenames)
        
#         # Adicionar categorias fixas se não existirem
#         fixed_categories = ["general", "agendamento", "procedimentos", "financeiro", "pessoal"]
#         existing_categories = [c["id"] for c in formatted_categories]
        
#         for category in fixed_categories:
#             if category not in existing_categories:
#                 formatted_categories.append({
#                     "id": category,
#                     "name": category.capitalize(),
#                     "document_count": 0
#                 })
        
#         # Retornar com total geral
#         return {
#             "categories": formatted_categories,
#             "total_documents": len(all_filenames)
#         }
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Erro ao listar categorias: {str(e)}")

@router.get("/categories")
async def list_categories(
    tenant_id: int = Depends(get_tenant_id),
    current_user: User = Depends(get_current_active_user),
):
    """
    Lista categorias disponíveis para seleção.
    Combina categorias predefinidas com contagens de documentos existentes.
    """
    t = int(tenant_id) if tenant_id else 0
    if not current_user.is_superuser and current_user.tenant_id != t:
        raise HTTPException(status_code=403, detail="Sem permissão para acessar este tenant")
    
    try:
        # Obter contagem de documentos por categoria do RAG
        rag_service = RAGServiceFAISS(tenant_id=tenant_id)
        existing_categories = await rag_service.list_categories()
        
        # Obter documentos para contagem precisa
        documents = await rag_service.list_documents()
        
        # Contagem de documentos únicos por categoria
        unique_filenames_by_category = {}
        
        for doc in documents:
            category = doc.get("category", "general")
            filename = doc.get("filename", "unknown")
            
            if category not in unique_filenames_by_category:
                unique_filenames_by_category[category] = set()
                
            unique_filenames_by_category[category].add(filename)
        
        # Contagem por categoria
        category_counts = {
            category: len(filenames)
            for category, filenames in unique_filenames_by_category.items()
        }
        
        # Combinar categorias predefinidas com contagens
        formatted_categories = []
        for category in DEFAULT_CATEGORIES:
            category_id = category["id"]
            count = category_counts.get(category_id, 0)
            
            formatted_categories.append({
                "id": category_id,
                "name": category["name"],
                "description": category["description"],
                "document_count": count
            })
        
        # Calcular total de documentos únicos
        all_filenames = set()
        for filenames in unique_filenames_by_category.values():
            all_filenames.update(filenames)
        
        # Retornar com total geral
        return {
            "categories": formatted_categories,
            "total_documents": len(all_filenames)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao listar categorias: {str(e)}")

    
@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: str,
    tenant_id: int = Depends(get_tenant_id),
    current_user: User = Depends(get_current_active_user),
):
    """
    Exclui um documento do RAG
    """
    # Verificar permissão
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Somente administradores podem excluir documentos")
    
    # Inicializar serviço RAG
    rag_service = RAGServiceFAISS(tenant_id=tenant_id)
    
    try:
        # Excluir documento
        success = await rag_service.delete_document(document_id)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Documento {document_id} não encontrado")
        
        return {"status": "success", "message": "Documento excluído com sucesso"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao excluir documento: {str(e)}")