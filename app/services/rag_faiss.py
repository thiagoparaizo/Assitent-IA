# \app\services\rag_faiss.py
import asyncio
import logging
import os
from typing import Any, Dict, List, Optional
import httpx
from langchain_openai import OpenAIEmbeddings
from langchain.vectorstores import FAISS
from langchain.text_splitter import CharacterTextSplitter
from langchain.document_loaders import TextLoader, PyPDFLoader
from langchain.schema import Document
from app.core.config import Settings, settings
from app.services.llm.factory import LLMServiceFactory
from app.db.session import SessionLocal


logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("app.services.rag")

class RAGServiceFAISS:
    """
    Serviço de Retrieval-Augmented Generation (RAG) com suporte multi-tenant usando FAISS
    """
    
    def __init__(self, tenant_id: int = None, vector_db_path: str = None, openai_api_key: str = None):
        self.tenant_id = tenant_id
        self.base_vector_db_path = vector_db_path or settings.VECTOR_DB_PATH
        self.db = SessionLocal()
        
        # Se temos um tenant_id, personalizar o caminho
        if tenant_id:
            self.vector_db_path = os.path.join(self.base_vector_db_path, f"tenant_{tenant_id}")
        else:
            self.vector_db_path = os.path.join(self.base_vector_db_path, "shared")
        
        # Criar diretório para o vectorstore se não existir
        os.makedirs(self.vector_db_path, exist_ok=True)
        
        # Inicializar o embedding model de forma assíncrona
        # Não inicializamos imediatamente para permitir a inicialização
        # adequada com o LLM do tenant
        self.embeddings = None
        self.vectorstore = None
        
        # Verificar se já existe um index para este tenant
        index_file = os.path.join(self.vector_db_path, "index.faiss")
        if os.path.exists(index_file):
            # Adiaremos o carregamento até precisarmos usar o vectorstore
            # para garantir que usamos os embeddings corretos
            pass
        
    def _create_faiss_from_documents(self, texts, embeddings):
        """
        A synchronous method to create FAISS from documents
        """
        return FAISS.from_documents(texts, embeddings)

    def _update_faiss_index(self, texts):
        """
        A synchronous method to update FAISS index
        """
        # Create a new temporary vectorstore
        temp_vectorstore = FAISS.from_documents(texts, self.embeddings)
        
        # Merge with existing vectorstore
        self.vectorstore.merge_from(temp_vectorstore)
        
        # Save changes
        self.vectorstore.save_local(self.vector_db_path, "index")    
    
    
    async def _init_embeddings(self):
        """
        Inicializa o modelo de embeddings com base nas configurações do tenant
        """
        if self.embeddings is not None:
            return
        
        # Usar o factory para criar o serviço LLM correto para o tenant
        llm_service = await LLMServiceFactory.create_service(self.db, tenant_id=self.tenant_id)
        
        # Option 1: Use a direct implementation of OpenAIEmbeddings (most reliable)
        # This is the preferred option for a production environment
        self.embeddings = OpenAIEmbeddings(
            openai_api_key=llm_service.api_key,
            model="text-embedding-ada-002"
        )
        
        
    class EmbeddingAdapter:
        def __init__(self, llm_service):
            self.llm_service = llm_service
            self._loop = asyncio.get_event_loop()
        
        async def async_embed_documents(self, texts):
            """Async method to get embeddings for documents"""
            embeddings = []
            for text in texts:
                embedding = await self.llm_service.get_embeddings(text)
                embeddings.append(embedding)
            return embeddings
        
        async def async_embed_query(self, text):
            """Async method to get embedding for a single query"""
            return await self.llm_service.get_embeddings(text)
        
        # Synchronous methods required by FAISS
        def embed_documents(self, texts):
            """
            Synchronous method that uses run_in_executor to call the async method
            without creating a new event loop
            """
            # Use a ThreadPoolExecutor to run the async method in a separate thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = self._loop.run_in_executor(
                    executor,
                    lambda: asyncio.run_coroutine_threadsafe(
                        self.async_embed_documents(texts), 
                        self._loop
                    ).result()
                )
                # Get result from future
                return self._loop.run_until_complete(future)
        
        def embed_query(self, text):
            """
            Synchronous method that uses run_in_executor to call the async method
            without creating a new event loop
            """
            # Use a ThreadPoolExecutor to run the async method in a separate thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = self._loop.run_in_executor(
                    executor,
                    lambda: asyncio.run_coroutine_threadsafe(
                        self.async_embed_query(text), 
                        self._loop
                    ).result()
                )
                # Get result from future
                return self._loop.run_until_complete(future)
    
    async def load_vectorstore(self):
        """
        Carrega o vectorstore do disco se existir
        """
        if not self.embeddings:
            await self._init_embeddings()
        
        index_file = os.path.join(self.vector_db_path, "index.faiss")
        if os.path.exists(index_file):
            try:
                # Run FAISS load operation in a separate thread to avoid event loop issues
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    self.vectorstore = await asyncio.get_event_loop().run_in_executor(
                        executor,
                        lambda: FAISS.load_local(
                            self.vector_db_path,
                            self.embeddings,
                            "index",
                            allow_dangerous_deserialization=True
                        )
                    )
                return True
            except Exception as e:
                print(f"Erro ao carregar vectorstore: {e}")
                return False
        return False
    
    async def index_documents(self, documents_dir: str, category: str = None, tenant_id: int = None) -> int:
        """
        Indexa documentos de um diretório para o vectorstore, mantendo os documentos existentes
        """
        # Permitir substituir o tenant_id no método
        if tenant_id is not None:
            self.tenant_id = tenant_id
            self.vector_db_path = os.path.join(self.base_vector_db_path, f"tenant_{tenant_id}")
            os.makedirs(self.vector_db_path, exist_ok=True)
            
            # Limpar embeddings para reinicializar com o tenant correto
            self.embeddings = None
        
        # Garantir que o modelo de embeddings está inicializado
        await self._init_embeddings()
        
        # Verificar e carregar vectorstore existente ANTES de processar novos documentos
        if self.vectorstore is None:
            index_file = os.path.join(self.vector_db_path, "index.faiss")
            if os.path.exists(index_file):
                success = await self.load_vectorstore()
                if not success:
                    print("Falha ao carregar vectorstore existente. Será criado um novo.")
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
                        
                        # Use a non-async method to load documents
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
            
            # Debug: mostrar número de documentos
            print(f"Processando {len(texts)} novos chunks de documentos.")
            
            # Run FAISS operations in a separate thread to avoid event loop issues
            import concurrent.futures
            
            with concurrent.futures.ThreadPoolExecutor() as executor:
                if self.vectorstore is None:
                    # Se não existir vectorstore, criar um novo
                    print("Criando novo vectorstore com os documentos processados")
                    self.vectorstore = await asyncio.get_event_loop().run_in_executor(
                        executor, self._create_faiss_from_documents, texts, self.embeddings
                    )
                    # Salvar alterações
                    self.vectorstore.save_local(self.vector_db_path, "index")
                else:
                    # Se já existir vectorstore, adicionar os novos documentos
                    print(f"Adicionando novos documentos ao vectorstore existente")
                    
                    # Versão mais direta: usar add_documents no executor
                    await asyncio.get_event_loop().run_in_executor(
                        executor,
                        lambda: self._safe_add_documents(texts)
                    )
                    
                    # Contar documentos após adição para verificar
                    doc_count = len(self.vectorstore.docstore._dict.keys())
                    print(f"Total de documentos após adição: {doc_count}")
            
            return len(texts)
        
        return 0
        
    async def add_text(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Adiciona um texto ao vectorstore
        """
        # Garantir que o modelo de embeddings está inicializado
        await self._init_embeddings()
        
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
        self.vectorstore.save_local(self.vector_db_path, "index")
    
    async def get_context(self, question: str, category: str = None, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Busca documentos relevantes para uma pergunta
        """
        # Garantir que o vectorstore está carregado
        if self.vectorstore is None:
            await self.load_vectorstore()
            
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
        
        # Usar o factory para obter o serviço LLM apropriado para o tenant
        llm_service = await LLMServiceFactory.create_service(self.db, tenant_id=self.tenant_id)
        
        # Preparar mensagens para o LLM
        messages = [
            {"role": "system", "content": "Você é um assistente de uma clínica odontológica. Responda de forma clara, precisa e amigável."},
            {"role": "user", "content": f"""
            Contexto: {context_text}
            
            Com base no contexto acima, responda à seguinte pergunta de forma clara e direta:
            Pergunta: {question}
            """}
        ]
        
        try:
            # Gerar resposta usando o serviço LLM escolhido para o tenant
            response = await llm_service.generate_response(messages)
            return response
        except Exception as e:
            print(f"Erro ao gerar resposta: {e}")
            return "Desculpe, não foi possível gerar uma resposta neste momento."
        
    async def list_documents(self, category: str = None, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Lista documentos indexados no vectorstore
        """
        if self.vectorstore is None:
            print("Vectorstore não inicializado. Tentando recarregar...")
            await self.load_vectorstore()
            
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
    
    async def search(self, query: str, category: str = None, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Método para buscar documentos relevantes para uma consulta.
        Este é um alias para get_context para compatibilidade com o orchestrator.
        
        Args:
            query: A consulta/mensagem do usuário
            category: A categoria para filtrar os resultados (opcional)
            limit: Número máximo de resultados a retornar
            
        Returns:
            Lista de documentos relevantes com suas pontuações
        """
        print(f"RAGServiceFAISS.search: Buscando por '{query}' na categoria '{category}' com limite {limit}")
        return await self.get_context(question=query, category=category, top_k=limit)
    
    async def delete_document(self, document_id: str) -> bool:
        """
        Exclui um documento do vectorstore
        """
        if self.vectorstore is None:
            # Tentar carregar o vectorstore se não estiver inicializado
            success = await self.load_vectorstore()
            if not success:
                print("Falha ao carregar vectorstore para exclusão de documento")
                return False
        
        try:
            # Verificar se o documento existe
            print(f"Tentando excluir documento com ID: {document_id}")
            
            # Verificar antes se o documento existe
            try:
                doc = self.vectorstore.docstore.search(document_id)
                
                # Verificar se o tenant_id corresponde
                if self.tenant_id is not None:
                    doc_tenant_id = doc.metadata.get("tenant_id")
                    if doc_tenant_id != self.tenant_id and str(doc_tenant_id) != str(self.tenant_id):
                        print(f"Documento {document_id} pertence ao tenant {doc_tenant_id}, não ao tenant {self.tenant_id}")
                        return False
                
                # Contagem antes da exclusão
                doc_count_before = len(self.vectorstore.docstore._dict.keys())
                print(f"Documentos antes da exclusão: {doc_count_before}")
                
                # Excluir documento - verificar a API correta
                if hasattr(self.vectorstore, 'delete'):
                    # Para versões mais recentes do FAISS
                    self.vectorstore.delete([document_id])
                elif hasattr(self.vectorstore, 'delete_by_document_id'):
                    # Para versões mais antigas do FAISS
                    self.vectorstore.delete_by_document_id(document_id)
                else:
                    # Tentar uma abordagem alternativa usando o docstore diretamente
                    if document_id in self.vectorstore.docstore._dict:
                        del self.vectorstore.docstore._dict[document_id]
                        print(f"Documento {document_id} excluído manualmente do docstore")
                    else:
                        print(f"Documento {document_id} não encontrado no docstore")
                        return False
                
                # Contagem após a exclusão
                doc_count_after = len(self.vectorstore.docstore._dict.keys())
                print(f"Documentos após a exclusão: {doc_count_after}")
                
                # Verificar se o número de documentos diminuiu
                if doc_count_after >= doc_count_before:
                    print("AVISO: O número de documentos não diminuiu após a exclusão!")
                
                # Salvar alterações
                self.vectorstore.save_local(self.vector_db_path, "index")
                
                print(f"Documento {document_id} excluído com sucesso")
                return True
            except Exception as e:
                print(f"Erro ao buscar documento {document_id}: {str(e)}")
                return False
        except Exception as e:
            print(f"Erro ao excluir documento: {e}")
            return False
        
        
    def _add_texts_to_faiss(self, texts):
        """
        Método síncrono para adicionar textos ao FAISS existente sem substituir
        """
        # Use add_documents para preservar documentos existentes
        self.vectorstore.add_documents(texts)
        
        # Salvar alterações
        self.vectorstore.save_local(self.vector_db_path, "index")
        
    def _safe_add_documents(self, texts):
        """
        Adiciona documentos ao FAISS de forma segura e salva após a adição
        """
        try:
            # Contar documentos antes
            doc_count_before = len(self.vectorstore.docstore._dict.keys())
            print(f"Documentos antes da adição: {doc_count_before}")
            
            # Adicionar documentos
            self.vectorstore.add_documents(texts)
            
            # Contar documentos depois
            doc_count_after = len(self.vectorstore.docstore._dict.keys())
            print(f"Documentos após a adição: {doc_count_after}")
            
            # Verificar se o número de documentos aumentou
            if doc_count_after <= doc_count_before:
                print("AVISO: O número de documentos não aumentou após a adição!")
            
            # Salvar o vectorstore para persistir os novos documentos
            self.vectorstore.save_local(self.vector_db_path, "index")
            return True
        except Exception as e:
            print(f"Erro ao adicionar documentos ao vectorstore: {e}")
            return False