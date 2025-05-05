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

router = APIRouter()


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
    if not current_user.is_superuser and current_user.tenant_id != tenant_id:
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
        num_chunks = rag_service.index_documents(temp_dir, category=category)
        
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
    Lista documentos indexados no RAG
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
        
        # Retornar lista de documentos
        return {
            "documents": documents,
            "total": len(documents),
            "skip": skip,
            "limit": limit
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao listar documentos: {str(e)}")
    
@router.get("/categories")
async def list_categories(
    tenant_id: int = Depends(get_tenant_id),
    current_user: User = Depends(get_current_active_user),
):
    """
    Lista categorias disponíveis no RAG
    """
    t = int(tenant_id) if tenant_id else 0
    if not current_user.is_superuser and current_user.tenant_id != t:
        raise HTTPException(status_code=403, detail="Sem permissão para acessar este tenant")
    
    # Inicializar serviço RAG
    rag_service = RAGServiceFAISS(tenant_id=tenant_id)
    
    try:
        # Obter categorias
        categories = await rag_service.list_categories()
        
        # Formatar categorias
        formatted_categories = [
            {
                "id": category,
                "name": category.capitalize(),
                "document_count": count
            }
            for category, count in categories.items()
        ]
        
        # Adicionar categorias fixas se não existirem
        fixed_categories = ["general", "agendamento", "procedimentos", "financeiro"]
        existing_categories = [c["id"] for c in formatted_categories]
        
        for category in fixed_categories:
            if category not in existing_categories:
                formatted_categories.append({
                    "id": category,
                    "name": category.capitalize(),
                    "document_count": 0
                })
        
        return {"categories": formatted_categories}
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