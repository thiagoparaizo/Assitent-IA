from datetime import datetime
import os
from typing import List, Optional, Dict, Any

import chromadb
import httpx
from langchain.embeddings import OpenAIEmbeddings
from langchain.text_splitter import CharacterTextSplitter
from langchain.vectorstores import Chroma
from langchain.document_loaders import TextLoader, DirectoryLoader
from langchain.schema import Document
from docling_core.types import DoclingDocument
from docling.document_converter import DocumentConverter


from app.core.config import Settings, settings

from langchain.document_loaders import TextLoader, DirectoryLoader, PyPDFLoader, UnstructuredMarkdownLoader


class RAGService:
    """
    Serviço de Retrieval-Augmented Generation (RAG) com suporte multi-tenant e Docling
    """
    
    def __init__(self, tenant_id: int = None, vector_db_path: str = None):
        self.tenant_id = tenant_id
        
        # Configurações para o PostgreSQL
        self.collection_name = f"tenant_{tenant_id}_collection" if tenant_id else "shared_collection"
        
        # Configurar cliente Chroma para usar PostgreSQL
        self.client = chromadb.PersistentClient(
            path="/path/to/persist",
            settings=chromadb.Settings(
                persist_directory="/path/to/persist",
                postgres_connection_string="postgresql://postgres:postgres@localhost:5432/assistant"
            )
        )
        
        # Inicializar embedding
        self.embeddings = OpenAIEmbeddings(api_key=settings.OPENAI_API_KEY)
        
        # Tentar obter a collection ou criar uma nova
        try:
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"tenant_id": self.tenant_id} if self.tenant_id else {}
            )
            
            # Inicializar o vectorstore
            self.vectorstore = Chroma(
                client=self.client,
                collection_name=self.collection_name,
                embedding_function=self.embeddings
            )
        except Exception as e:
            print(f"Erro ao inicializar Chroma com PostgreSQL: {e}")
            self.vectorstore = None
    
    def load_vectorstore(self):
        """
        Carrega o vectorstore existente
        """
        self.vectorstore = Chroma(
            persist_directory=self.vector_db_path,
            embedding_function=self.embeddings
        )
        
    # def index_documents(self, documents_dir: str, category: str = None, tenant_id: int = None) -> int:
    #     """
    #     Indexa documentos de um diretório para o vectorstore usando carregadores nativos do LangChain
    #     """
    #     # Atualizar tenant_id se necessário
    #     if tenant_id is not None:
    #         self.tenant_id = tenant_id
    #         self.vector_db_path = os.path.join(self.base_vector_db_path, f"tenant_{tenant_id}")
    #         os.makedirs(self.vector_db_path, exist_ok=True)
            
    #         # Recarregar vectorstore
    #         if os.path.exists(os.path.join(self.vector_db_path, "chroma.sqlite3")):
    #             self.load_vectorstore()
    #         else:
    #             self.vectorstore = None
                
    #     # Dicionário de carregadores por extensão
    #     loaders = {
    #         ".txt": (lambda path: TextLoader(path, encoding='utf-8')),
    #         ".md": (lambda path: UnstructuredMarkdownLoader(path)),
    #         ".pdf": (lambda path: PyPDFLoader(path)),
    #     }
        
    #     # Processar cada arquivo no diretório
    #     all_documents = []
        
    #     for root, _, files in os.walk(documents_dir):
    #         for file in files:
    #             file_path = os.path.join(root, file)
    #             _, ext = os.path.splitext(file)
                
    #             if ext.lower() in loaders:
    #                 try:
    #                     # Usar o carregador apropriado
    #                     loader = loaders[ext.lower()](file_path)
    #                     documents = loader.load()
                        
    #                     # Adicionar metadados
    #                     for doc in documents:
    #                         doc.metadata["tenant_id"] = self.tenant_id
    #                         doc.metadata["filename"] = file
    #                         doc.metadata["source"] = file_path
    #                         if category:
    #                             doc.metadata["category"] = category
                        
    #                     all_documents.extend(documents)
    #                 except Exception as e:
    #                     print(f"Erro ao processar arquivo {file_path}: {e}")
        
    #     # Dividir em chunks menores
    #     if all_documents:
    #         text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    #         texts = text_splitter.split_documents(all_documents)
            
    #         # Adicionar ao vectorstore
    #         if self.vectorstore is None:
    #             self.vectorstore = Chroma.from_documents(
    #                 documents=texts,
    #                 embedding=self.embeddings,
    #                 persist_directory=self.vector_db_path
    #             )
    #         else:
    #             self.vectorstore.add_documents(texts)
            
    #         # Salvar alterações
    #         self.vectorstore.persist()
            
    #         return len(texts)
        
    #     return 0
    def index_documents(self, documents_dir: str, category: str = None, tenant_id: int = None) -> int:
        """
        Indexa documentos de um diretório para o vectorstore usando PostgreSQL
        """
        # Atualizar tenant_id se necessário
        if tenant_id is not None and tenant_id != self.tenant_id:
            self.tenant_id = tenant_id
            self.collection_name = f"tenant_{tenant_id}_collection"
            
            # Reinicializar com a nova collection
            try:
                self.collection = self.client.get_or_create_collection(
                    name=self.collection_name,
                    metadata={"tenant_id": self.tenant_id}
                )
                
                self.vectorstore = Chroma(
                    client=self.client,
                    collection_name=self.collection_name,
                    embedding_function=self.embeddings
                )
            except Exception as e:
                print(f"Erro ao reinicializar Chroma para tenant {tenant_id}: {e}")
                return 0
                
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
                return 0
                
            self.vectorstore.add_documents(texts)
            return len(texts)
        
        return 0
    
    async def get_context(self, question: str, category: str = None, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Busca documentos relevantes para uma pergunta
        """
        if self.vectorstore is None:
            return []
        
        # Preparar filtro de metadados
        where_document = {}
        
        # Adicionar filtro de tenant_id se aplicável
        if self.tenant_id is not None:
            where_document["tenant_id"] = self.tenant_id
        
        # Adicionar filtro de categoria se fornecido
        if category:
            where_document["category"] = category
        
        # Fazer a busca com filtro de metadados
        docs = self.vectorstore.similarity_search(
            question, 
            k=top_k,
            where_document=where_document
        )
        
        # Formatar resultados
        results = []
        for i, doc in enumerate(docs):
            results.append({
                "content": doc.page_content,
                "metadata": doc.metadata,
                "relevance_score": 1.0 - (i * 0.1),  # Simulação de score
            })
        
        return results
        
    
from docling.document_converter import DocumentConverter
from langchain.schema import Document
import os
from typing import List

class SeuProcessador:
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id

    def process_file_with_docling(self, file_path: str) -> List[Document]:
        """
        Processa um arquivo usando o Docling e retorna documentos formatados para RAG.
        """
        converter = DocumentConverter()
        result = converter.convert(file_path)
        doc = result.document  # DoclingDocument

        # Metadados base
        base_metadata = {
            "source": file_path,
            "filename": os.path.basename(file_path),
            "tenant_id": self.tenant_id,
            "docling_id": f"{doc.name}_{int(datetime.now().timestamp())}",
        }

        documents = []

        # Iterar pelas seções do documento
        for i, section in enumerate(doc.sections):
            metadata = base_metadata.copy()
            metadata.update({
                "section_index": i,
                "section_title": getattr(section, "title", None),
                "page": getattr(section, "page", None),
                "content_type": "text"
            })

            documents.append(Document(
                page_content=section.text,
                metadata=metadata
            ))

            # Se houver tabelas, incluir como documentos separados
            if getattr(section, "tables", None):
                for j, table in enumerate(section.tables):
                    table_metadata = metadata.copy()
                    table_metadata.update({
                        "content_type": "table",
                        "table_index": j,
                    })
                    documents.append(Document(
                        page_content=str(table),
                        metadata=table_metadata
                    ))

        return documents
    
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
            if os.path.exists(os.path.join(self.vector_db_path, "chroma.sqlite3")):
                self.load_vectorstore()
            else:
                self.vectorstore = None
        
        # Listar todos os arquivos no diretório
        all_files = []
        for root, _, files in os.walk(documents_dir):
            for file in files:
                all_files.append(os.path.join(root, file))
        
        # Processar cada arquivo com o Docling
        all_documents = []
        for file_path in all_files:
            try:
                # Adicionar categoria ao metadados, se fornecida
                documents = self.process_file_with_docling(file_path)
                
                # Adicionar categoria a cada documento
                if category:
                    for doc in documents:
                        doc.metadata["category"] = category
                
                all_documents.extend(documents)
            except Exception as e:
                print(f"Erro ao processar arquivo {file_path}: {e}")
        
        # Dividir documentos em chunks se necessário
        text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        texts = text_splitter.split_documents(all_documents)
        
        # Criar ou atualizar o vectorstore
        if self.vectorstore is None:
            self.vectorstore = Chroma.from_documents(
                documents=texts,
                embedding=self.embeddings,
                persist_directory=self.vector_db_path
            )
        else:
            self.vectorstore.add_documents(texts)
        
        # Salvar o vectorstore
        self.vectorstore.persist()
        
        return len(texts)
    
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
            self.vectorstore = Chroma.from_documents(
                documents=documents,
                embedding=self.embeddings,
                persist_directory=self.vector_db_path
            )
        else:
            self.vectorstore.add_documents(documents)
        
        # Salvar o vectorstore
        self.vectorstore.persist()
        
    async def get_context(self, question: str, category: str = None, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Busca documentos relevantes para uma pergunta
        """
        if self.vectorstore is None:
            return []
        
        # Preparar filtro de metadados
        metadata_filter = {}
        
        # Adicionar filtro de tenant_id se aplicável
        if self.tenant_id is not None:
            metadata_filter["tenant_id"] = self.tenant_id
        
        # Adicionar filtro de categoria se fornecido
        if category:
            metadata_filter["category"] = category
        
        # Buscar documentos relevantes com filtro
        if metadata_filter:
            docs = self.vectorstore.similarity_search(
                question, 
                k=top_k,
                filter=metadata_filter
            )
        else:
            docs = self.vectorstore.similarity_search(question, k=top_k)
        
        # Formatar resultados
        results = []
        for i, doc in enumerate(docs):
            results.append({
                "content": doc.page_content,
                "metadata": doc.metadata,
                "relevance_score": 1.0 - (i * 0.1),  # Simulação de score
            })
        
        return results
    
    def query(self, question: str, top_k: int = 5) -> List[dict]:
        """
        Busca documentos relevantes para uma pergunta
        """
        if self.vectorstore is None:
            return []
        
        # Buscar documentos relevantes
        docs = self.vectorstore.similarity_search(question, k=top_k)
        
        # Formatar resultados
        results = []
        for i, doc in enumerate(docs):
            results.append({
                "content": doc.page_content,
                "metadata": doc.metadata,
                "relevance_score": 1.0 - (i * 0.1),  # Simulação de score
            })
        
        return results
    
    def answer(self, question: str) -> str:
        """
        Responde a uma pergunta usando o RAG
        """
        if self.qa_chain is None:
            return "Não tenho informações suficientes para responder a essa pergunta."
        
        # Obter resposta do QA chain
        result = self.qa_chain({"query": question})
        
        return result["result"]
    
    def load_vectorstore(self):
        """
        Carrega o vectorstore existente
        """
        self.vectorstore = Chroma(
            persist_directory=self.vector_db_path,
            embedding_function=self.embeddings
        )
    
    # async def get_context(self, question: str, top_k: int = 5) -> List[Dict[str, Any]]:
    #     """
    #     Busca documentos relevantes para uma pergunta
    #     """
    #     if self.vectorstore is None:
    #         return []
        
    #     # Buscar documentos relevantes
    #     docs = self.vectorstore.similarity_search(question, k=top_k)
        
    #     # Formatar resultados
    #     results = []
    #     for i, doc in enumerate(docs):
    #         results.append({
    #             "content": doc.page_content,
    #             "metadata": doc.metadata,
    #             "relevance_score": 1.0 - (i * 0.1),  # Simulação de score
    #         })
        
    #     return results
    
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
                        "max_tokens": 500
                    },
                    timeout=30.0
                )
                
                response.raise_for_status()
                data = response.json()
                
                return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            print(f"Erro ao gerar resposta: {e}")
            return "Desculpe, não foi possível gerar uma resposta neste momento."