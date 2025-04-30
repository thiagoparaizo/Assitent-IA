# app/api/endpoints/knowledge.py
from datetime import datetime, time
import os
import shutil
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, get_db
from app.db.models.user import User
from app.services.rag import RAGService

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
    temp_dir = f"./storage/temp/{tenant_id}_{category}_{int(time.time())}"
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
        rag_service = RAGService(tenant_id=tenant_id)
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
    rag_service = RAGService()
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