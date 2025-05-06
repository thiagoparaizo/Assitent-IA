import os
from typing import Any, Dict, List, Optional
import httpx
from langchain_openai import OpenAIEmbeddings
from langchain.vectorstores import FAISS
from langchain.text_splitter import CharacterTextSplitter
from langchain.document_loaders import TextLoader, PyPDFLoader
from langchain.schema import Document
from app.core.config import Settings, settings

class RAGServiceFAISS:
    """
    Serviço de Retrieval-Augmented Generation (RAG) com suporte multi-tenant usando FAISS
    """
    
    def __init__(self, tenant_id: int = None, vector_db_path: str = None, openai_api_key: str = None):
        self.tenant_id = tenant_id
        self.base_vector_db_path = vector_db_path or settings.VECTOR_DB_PATH
        
        # Se temos um tenant_id, personalizar o caminho
        if tenant_id:
            self.vector_db_path = os.path.join(self.base_vector_db_path, f"tenant_{tenant_id}")
        else:
            self.vector_db_path = os.path.join(self.base_vector_db_path, "shared")
        
        # Criar diretório para o vectorstore se não existir
        os.makedirs(self.vector_db_path, exist_ok=True)
        
        # Inicializar o embedding model
        self.embeddings = OpenAIEmbeddings(api_key=openai_api_key or settings.OPENAI_API_KEY)
        self.vectorstore = None
        
        # Verificar se já existe um index para este tenant
        index_file = os.path.join(self.vector_db_path, "index.faiss")
        if os.path.exists(index_file):
            self.load_vectorstore()
    
    def load_vectorstore(self):
        """
        Carrega o vectorstore existente
        """
        try:
            self.vectorstore = FAISS.load_local(
                self.vector_db_path, 
                self.embeddings, 
                "index",
                allow_dangerous_deserialization=True  # Adicione esta opção
            )
        except Exception as e:
            print(f"Erro ao carregar vectorstore: {e}")
            self.vectorstore = None
    
    def index_documents(self, documents_dir: str, category: str = None, tenant_id: int = None) -> int:
        """
        Indexa documentos de um diretório para o vectorstore
        """
        # Permitir substituir o tenant_id no método
        if tenant_id is not None:
            self.tenant_id = tenant_id
            self.vector_db_path = os.path.join(self.base_vector_db_path, f"tenant_{tenant_id}")
            os.makedirs(self.vector_db_path, exist_ok=True)
            
            # Recarregar vectorstore com o novo caminho
            index_file = os.path.join(self.vector_db_path, "index.faiss")
            if os.path.exists(index_file):
                self.load_vectorstore()
            else:
                self.vectorstore = None
        
        # Dicionário de carregadores por extensão
        loaders = {
            ".txt": (lambda path: TextLoader(path, encoding='utf-8')),
            ".md": (lambda path: TextLoader(path, encoding='utf-8')),
            ".pdf": (lambda path: PyPDFLoader(path)),
        }
        
        # Processar cada arquivo no diretório
        all_documents = []
        
        for root, _, files in os.walk(documents_dir):
            for file in files:
                file_path = os.path.join(root, file)
                _, ext = os.path.splitext(file)
                
                if ext.lower() in loaders:
                    try:
                        # Usar o carregador apropriado
                        loader = loaders[ext.lower()](file_path)
                        documents = loader.load()
                        
                        # Adicionar metadados
                        for doc in documents:
                            doc.metadata["tenant_id"] = self.tenant_id
                            doc.metadata["filename"] = file
                            doc.metadata["source"] = file_path
                            if category:
                                doc.metadata["category"] = category
                        
                        all_documents.extend(documents)
                    except Exception as e:
                        print(f"Erro ao processar arquivo {file_path}: {e}")
        
        # Dividir em chunks menores
        if all_documents:
            text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
            texts = text_splitter.split_documents(all_documents)
            
            # Adicionar ao vectorstore
            if self.vectorstore is None:
                # Criar um novo vectorstore
                self.vectorstore = FAISS.from_documents(texts, self.embeddings)
                # Salvar alterações
                self.vectorstore.save_local(self.vector_db_path, "index", allow_dangerous_deserialization=True)
            else:
                # Atualizar o vectorstore existente
                # Aqui está a correção: criar um novo vectorstore temporário
                temp_vectorstore = FAISS.from_documents(texts, self.embeddings)
                
                # Mesclar com o vectorstore existente
                self.vectorstore.merge_from(temp_vectorstore)
                
                # Salvar alterações
                self.vectorstore.save_local(self.vector_db_path, "index")
            
            return len(texts)
        
        return 0
        
    def add_text(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Adiciona um texto ao vectorstore
        """
        # Garantir que tenant_id esteja nos metadados
        if metadata is None:
            metadata = {}
        
        if self.tenant_id is not None and "tenant_id" not in metadata:
            metadata["tenant_id"] = self.tenant_id
        
        # Dividir texto em chunks
        text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        chunks = text_splitter.split_text(text)
        
        # Criar documentos com os chunks
        documents = [Document(page_content=chunk, metadata=metadata) for chunk in chunks]
        
        # Adicionar documentos ao vectorstore
        if self.vectorstore is None:
            self.vectorstore = FAISS.from_documents(documents, self.embeddings)
        else:
            self.vectorstore = self.vectorstore.add_documents(documents)
        
        # Salvar o vectorstore
        self.vectorstore.save_local(self.vector_db_path, "index", allow_dangerous_deserialization=True)
    
    async def get_context(self, question: str, category: str = None, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Busca documentos relevantes para uma pergunta
        """
        if self.vectorstore is None:
            return []
        
        # FAISS não suporta filtragem direta como o Chroma
        # Vamos buscar mais resultados e filtrar depois
        docs_with_scores = self.vectorstore.similarity_search_with_score(question, k=top_k * 3)
        
        # Filtrar por metadados
        filtered_docs = []
        for doc, score in docs_with_scores:
            # Verificar tenant_id
            if self.tenant_id is not None:
                doc_tenant_id = doc.metadata.get("tenant_id")
                if doc_tenant_id != self.tenant_id and doc_tenant_id != str(self.tenant_id):
                    continue
                
            # Verificar categoria se fornecida
            if category and doc.metadata.get("category") != category:
                continue
                
            filtered_docs.append((doc, score))
            
            # Limitar ao número desejado
            if len(filtered_docs) >= top_k:
                break
        
        # Formatar resultados
        results = []
        for i, (doc, score) in enumerate(filtered_docs[:top_k]):
            results.append({
                "content": doc.page_content,
                "metadata": doc.metadata,
                "relevance_score": 1.0 / (1.0 + score),  # Converter para um score entre 0 e 1
            })
        
        return results
    
    async def get_answer(self, question: str, context: List[dict] = None) -> str:
        """
        Gera uma resposta usando o contexto recuperado
        """
        # Se não tiver contexto, buscar
        if context is None:
            context = await self.get_context(question)
        
        # Se ainda não tiver contexto, retornar mensagem padrão
        if not context:
            return "Não tenho informações suficientes para responder a essa pergunta."
        
        # Montar o contexto para a requisição
        context_text = "\n\n".join([f"Documento {i+1}:\n{doc['content']}" for i, doc in enumerate(context)])
        
        # Preparar prompt para a API do OpenAI
        prompt = f"""
        Contexto: {context_text}
        
        Com base no contexto acima, responda à seguinte pergunta de forma clara e direta:
        Pergunta: {question}
        
        Resposta:
        """
        
        # Fazer requisição para a API do OpenAI
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "gpt-3.5-turbo",
                        "messages": [
                            {"role": "system", "content": "Você é um assistente de uma clínica odontológica. Responda de forma clara, precisa e amigável."},
                            {"role": "user", "content": prompt}
                        ],
                        "max_tokens":.500
                    },
                    timeout=30.0
                )
                
                response.raise_for_status()
                data = response.json()
                
                return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            print(f"Erro ao gerar resposta: {e}")
            return "Desculpe, não foi possível gerar uma resposta neste momento."
        
    async def list_documents(self, category: str = None, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Lista documentos indexados no vectorstore
        """
        if self.vectorstore is None:
            print("Vectorstore não inicializado. Tentando recarregar...")
            self.load_vectorstore()
            
            if self.vectorstore is None:
                print("Não foi possível carregar o vectorstore.")
                return []
        
        # Para FAISS, precisamos extrair informações dos metadados
        documents = []
        
        # Em FAISS, não temos uma função direta para listar documentos
        # Vamos precisar carregar o índice e extrair os documentos
        try:
            # Obtém todos os IDs dos documentos
            doc_ids = list(self.vectorstore.docstore._dict.keys())
            print(f"Total de documentos encontrados: {len(doc_ids)}")
            
            # Aplica skip e limit
            paginated_ids = doc_ids[skip:skip + limit]
            
            # Para cada ID, obtém o documento
            for doc_id in paginated_ids:
                doc = self.vectorstore.docstore.search(doc_id)
                
                # Se category for fornecido, filtra por categoria
                if category and doc.metadata.get("category") != category:
                    continue
                    
                # Se o tenant_id não corresponder, pula
                if self.tenant_id is not None:
                    doc_tenant_id = doc.metadata.get("tenant_id")
                    if doc_tenant_id != self.tenant_id and str(doc_tenant_id) != str(self.tenant_id):
                        continue
                
                # Formatar documento para resposta
                documents.append({
                    "id": doc_id,
                    "filename": doc.metadata.get("filename", "Unknown"),
                    "source": doc.metadata.get("source", ""),
                    "category": doc.metadata.get("category", ""),
                    "content_preview": doc.page_content[:100] + "..." if len(doc.page_content) > 100 else doc.page_content,
                    "metadata": doc.metadata
                })
        except Exception as e:
            print(f"Erro ao listar documentos: {e}")
            return []
        
        print(f"Documentos retornados após filtragem: {len(documents)}")
        return documents
    
    async def list_categories(self) -> Dict[str, int]:
        """
        Lista categorias disponíveis no vectorstore e conta documentos por categoria
        """
        if self.vectorstore is None:
            return {}
        
        categories = {}
        
        # Em FAISS, não temos uma função direta para listar categorias
        # Vamos iterar pelos documentos e contar as categorias
        try:
            # Obtém todos os IDs dos documentos
            doc_ids = list(self.vectorstore.docstore._dict.keys())
            
            # Para cada ID, obtém o documento
            for doc_id in doc_ids:
                doc = self.vectorstore.docstore.search(doc_id)
                
                # Se o tenant_id não corresponder, pula
                if self.tenant_id is not None:
                    doc_tenant_id = doc.metadata.get("tenant_id")
                    if doc_tenant_id != self.tenant_id and str(doc_tenant_id) != str(self.tenant_id):
                        continue
                
                # Obter categoria
                category = doc.metadata.get("category", "general")
                
                # Incrementar contador
                if category in categories:
                    categories[category] += 1
                else:
                    categories[category] = 1
        except Exception as e:
            print(f"Erro ao listar categorias: {e}")
            return {}
        
        return categories
    
    async def delete_document(self, document_id: str) -> bool:
        """
        Exclui um documento do vectorstore
        """
        if self.vectorstore is None:
            return False
        
        try:
            # Verificar se o documento existe
            doc = self.vectorstore.docstore.search(document_id)
            
            # Verificar se o tenant_id corresponde
            if self.tenant_id is not None:
                doc_tenant_id = doc.metadata.get("tenant_id")
                if doc_tenant_id != self.tenant_id and str(doc_tenant_id) != str(self.tenant_id):
                    return False
            
            # Excluir documento
            self.vectorstore.delete([document_id])
            
            # Salvar alterações
            self.vectorstore.save_local(self.vector_db_path, "index", allow_dangerous_deserialization=True)
            
            return True
        except Exception as e:
            print(f"Erro ao excluir documento: {e}")
            return False