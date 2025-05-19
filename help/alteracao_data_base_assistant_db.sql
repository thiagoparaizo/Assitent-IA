
-- Adicionar as colunas relacionadas a LLM na tabela tenants
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS default_llm_provider_id INTEGER;
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS default_llm_model_id INTEGER;
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS llm_api_key TEXT;

-- Adicionar as foreign keys
ALTER TABLE tenants 
  ADD CONSTRAINT fk_tenant_llm_provider 
  FOREIGN KEY (default_llm_provider_id) 
  REFERENCES llm_providers(id) 
  ON DELETE SET NULL;

ALTER TABLE tenants 
  ADD CONSTRAINT fk_tenant_llm_model 
  FOREIGN KEY (default_llm_model_id) 
  REFERENCES llm_models(id) 
  ON DELETE SET NULL;

-- Comentário: As constraints de foreign key só funcionarão se as tabelas llm_providers e llm_models já existirem.
-- Se essas tabelas ainda não existirem, você precisará criá-las primeiro.

-- Script SQL para Criar as Tabelas LLM (caso ainda não existam)
-- Se as tabelas llm_providers e llm_models ainda não existirem, você precisará criá-las primeiro:

sql-- Criar tabela llm_providers se não existir
CREATE TABLE IF NOT EXISTS llm_providers (
    id SERIAL PRIMARY KEY,
    name VARCHAR NOT NULL UNIQUE,
    provider_type VARCHAR NOT NULL,
    description TEXT,
    base_url VARCHAR,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Criar índice para llm_providers
CREATE INDEX IF NOT EXISTS ix_llm_providers_id ON llm_providers (id);

-- Inserir provedor OpenAI padrão
INSERT INTO llm_providers (name, provider_type, description, is_active)
SELECT 'OpenAI', 'openai', 'Modelos nativos da OpenAI (GPT-3.5, GPT-4, etc)', TRUE
WHERE NOT EXISTS (SELECT 1 FROM llm_providers WHERE name = 'OpenAI');

-- Criar tabela llm_models se não existir
CREATE TABLE IF NOT EXISTS llm_models (
    id SERIAL PRIMARY KEY,
    provider_id INTEGER NOT NULL,
    name VARCHAR NOT NULL,
    model_id VARCHAR NOT NULL,
    max_tokens INTEGER,
    default_temperature FLOAT DEFAULT 0.7,
    supports_functions BOOLEAN DEFAULT FALSE,
    supports_vision BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    cost_per_1k_tokens FLOAT DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_model_provider FOREIGN KEY (provider_id) REFERENCES llm_providers(id) ON DELETE CASCADE
);

-- Criar índice para llm_models
CREATE INDEX IF NOT EXISTS ix_llm_models_id ON llm_models (id);

-- Inserir modelos OpenAI padrão
INSERT INTO llm_models (provider_id, name, model_id, max_tokens, default_temperature, supports_functions, supports_vision, is_active, cost_per_1k_tokens)
SELECT 
    (SELECT id FROM llm_providers WHERE name = 'OpenAI'), 
    'GPT-4 Turbo', 
    'gpt-4-turbo', 
    4096, 
    0.7, 
    TRUE, 
    FALSE, 
    TRUE, 
    0.01
WHERE NOT EXISTS (SELECT 1 FROM llm_models WHERE model_id = 'gpt-4-turbo');

INSERT INTO llm_models (provider_id, name, model_id, max_tokens, default_temperature, supports_functions, supports_vision, is_active, cost_per_1k_tokens)
SELECT 
    (SELECT id FROM llm_providers WHERE name = 'OpenAI'), 
    'GPT-4o', 
    'gpt-4o', 
    8192, 
    0.7, 
    TRUE, 
    TRUE, 
    TRUE, 
    0.005
WHERE NOT EXISTS (SELECT 1 FROM llm_models WHERE model_id = 'gpt-4o');

INSERT INTO llm_models (provider_id, name, model_id, max_tokens, default_temperature, supports_functions, supports_vision, is_active, cost_per_1k_tokens)
SELECT 
    (SELECT id FROM llm_providers WHERE name = 'OpenAI'), 
    'GPT-3.5 Turbo', 
    'gpt-3.5-turbo', 
    4096, 
    0.7, 
    TRUE, 
    FALSE, 
    TRUE, 
    0.0015
WHERE NOT EXISTS (SELECT 1 FROM llm_models WHERE model_id = 'gpt-3.5-turbo');