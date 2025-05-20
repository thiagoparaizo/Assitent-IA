Visão Geral do Projeto
Este é um sistema de assistente virtual inteligente com as seguintes características principais:

Arquitetura multi-tenant: Suporta múltiplos clientes/organizações (tenants) isolados
Integração com WhatsApp: Permite interações via WhatsApp usando um serviço em Go
Sistema multiagente: Diferentes tipos de agentes especializados que podem transferir conversas entre si
RAG (Retrieval Augmented Generation): Usa bases de conhecimento por categoria e tenant
Suporte a múltiplos LLMs: Integração com vários provedores (OpenAI, Gemini, DeepSeek)
Interface administrativa: Painel web para gerenciar agentes, conhecimento, webhooks, dispositivos, etc.

Arquitetura do Sistema
O projeto parece seguir uma arquitetura moderna de microserviços:

API Backend (FastAPI): Serviço principal que gerencia a lógica de negócio
Serviço WhatsApp (Go): Microserviço separado para integração com WhatsApp
Admin Dashboard (Flask): Interface web para gerenciamento
PostgreSQL: Banco de dados principal
Redis: Cache e estado de conversas
Vector Database (FAISS): Armazenamento para embeddings do RAG

Componentes Principais
1. Sistema de Usuários e Tenants

Modelo multitenancy com isolamento de dados por tenant
Sistema de autenticação via JWT
Hierarquia de usuários (admin/superusuários e usuários normais)

2. Sistema de Agentes

Diferentes tipos: GENERAL, SPECIALIST, INTEGRATION, HUMAN, PERSONAL
Prompt dinâmico baseado em configuração
Sistema de escalação inteligente entre agentes
Integração com bases de conhecimento específicas

3. RAG (Retrieval Augmented Generation)

Implementação baseada em FAISS
Isolamento por tenant
Organização por categorias
Suporte a múltiplos tipos de documentos (PDF, texto, etc.)

4. Integração WhatsApp

Gestão de dispositivos e QR codes
Rastreamento de contatos
Filas de mensagens para gerenciar conversas
Webhook para eventos externos

5. LLM Factory

Design pattern Factory para criar serviços LLM dinamicamente
Suporta OpenAI, Google Gemini e DeepSeek
Configurável por tenant (API key, modelo padrão)

6. Memória e Orquestração

Serviço de memória para conversas passadas
Orquestrador para gerenciar fluxo entre agentes
Geração de sumários de conversas

Fluxo Principal

Uma mensagem chega via webhook do serviço WhatsApp
O sistema identifica o tenant e o dispositivo associado
O orquestrador determina qual agente deve responder
RAG é usado para obter contexto relevante da base de conhecimento
LLM gera uma resposta apropriada com o contexto
A resposta é enviada de volta ao usuário via WhatsApp
Opcionalmente, webhooks são acionados para sistemas externos

Recursos Destacados

Sistema de Filas: As mensagens são colocadas em uma fila para permitir contexto de múltiplas mensagens
Escalação Inteligente: O sistema pode transferir conversas para especialistas ou humanos
Persistência de Conversas: Conversas são arquivadas e podem ser analisadas posteriormente
Configuração Flexível: Sistema configurável por tenant e por agente
Integração MCP: Framework para chamadas de função pelos agentes

Aspectos Técnicos

Docker: Ambiente containerizado para fácil implantação
Async/Await: Uso extensivo de programação assíncrona em Python
Pydantic: Para validação de dados e definição de esquemas
SQLAlchemy: ORM para acesso ao banco de dados
Redis: Para cache e estado temporário
LangChain: Para construção de fluxos de RAG

Este sistema parece ser uma plataforma completa para criar assistentes virtuais personalizados que se conectam ao WhatsApp, com recursos avançados de IA e gerenciamento de conhecimento. A arquitetura é escalável e bem desenhada para suportar múltiplos clientes com diferentes necessidades e configurações.