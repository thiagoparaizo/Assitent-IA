CREATE TABLE token_usage_limits (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE,
    agent_id UUID REFERENCES agents(id) ON DELETE CASCADE,
    monthly_limit INTEGER NOT NULL,
    daily_limit INTEGER,
    warning_threshold FLOAT DEFAULT 0.8,
    notify_email VARCHAR,
    notify_webhook_url VARCHAR,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraint para garantir que ou tenant_id ou agent_id estão definidos
    CONSTRAINT chk_target CHECK (
        (tenant_id IS NOT NULL AND agent_id IS NULL) OR
        (tenant_id IS NULL AND agent_id IS NOT NULL) OR
        (tenant_id IS NOT NULL AND agent_id IS NOT NULL)
    )
);

-- Índices para melhor desempenho
CREATE INDEX idx_token_usage_limits_tenant ON token_usage_limits(tenant_id);
CREATE INDEX idx_token_usage_limits_agent ON token_usage_limits(agent_id);

---

CREATE TABLE token_usage_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    conversation_id VARCHAR,
    model_id INTEGER NOT NULL REFERENCES llm_models(id) ON DELETE CASCADE,
    prompt_tokens INTEGER NOT NULL,
    completion_tokens INTEGER NOT NULL,
    total_tokens INTEGER NOT NULL,
    estimated_cost_usd FLOAT DEFAULT 0.0,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índices para melhor desempenho e filtragem
CREATE INDEX idx_token_usage_logs_tenant ON token_usage_logs(tenant_id);
CREATE INDEX idx_token_usage_logs_agent ON token_usage_logs(agent_id);
CREATE INDEX idx_token_usage_logs_model ON token_usage_logs(model_id);
CREATE INDEX idx_token_usage_logs_conversation ON token_usage_logs(conversation_id);
CREATE INDEX idx_token_usage_logs_timestamp ON token_usage_logs(timestamp);

---
CREATE TABLE token_usage_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE,
    agent_id UUID REFERENCES agents(id) ON DELETE CASCADE,
    limit_type VARCHAR NOT NULL,
    threshold_value FLOAT NOT NULL,
    current_usage INTEGER NOT NULL,
    max_limit INTEGER NOT NULL,
    notification_sent BOOLEAN DEFAULT FALSE,
    notification_channel VARCHAR,
    notification_target VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índices para melhor desempenho
CREATE INDEX idx_token_usage_alerts_tenant ON token_usage_alerts(tenant_id);
CREATE INDEX idx_token_usage_alerts_agent ON token_usage_alerts(agent_id);
CREATE INDEX idx_token_usage_alerts_created_at ON token_usage_alerts(created_at);

---
------------------------sempre executar ----------------------
-- Adicionar trigger para atualizar campo updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Aplicar trigger na tabela de limites
CREATE TRIGGER trigger_update_token_usage_limits_updated_at
BEFORE UPDATE ON token_usage_limits
FOR EACH ROW
EXECUTE PROCEDURE update_updated_at_column();

---

-- Constraint para evitar múltiplos limites para o mesmo tenant sem agente específico
CREATE UNIQUE INDEX idx_unique_tenant_limit 
ON token_usage_limits (tenant_id) 
WHERE agent_id IS NULL;

-- Constraint para evitar múltiplos limites para a mesma combinação de tenant e agente
CREATE UNIQUE INDEX idx_unique_tenant_agent_limit 
ON token_usage_limits (tenant_id, agent_id) 
WHERE agent_id IS NOT NULL;

-- Função para atualizar limites de uso de tokens
CREATE OR REPLACE FUNCTION update_token_usage_limits_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger para atualizar o campo updated_at na tabela token_usage_limits
CREATE TRIGGER update_token_usage_limits_timestamp
BEFORE UPDATE ON token_usage_limits
FOR EACH ROW
EXECUTE FUNCTION update_token_usage_limits_updated_at();

CREATE OR REPLACE VIEW daily_token_usage_summary AS
SELECT 
    tenant_id,
    agent_id,
    DATE(timestamp) as usage_date,
    SUM(prompt_tokens) as prompt_tokens,
    SUM(completion_tokens) as completion_tokens,
    SUM(total_tokens) as total_tokens,
    SUM(estimated_cost_usd) as total_cost
FROM 
    token_usage_logs
GROUP BY 
    tenant_id, agent_id, DATE(timestamp)
ORDER BY 
    usage_date DESC;


    CREATE OR REPLACE VIEW monthly_token_usage_summary AS
SELECT 
    tenant_id,
    agent_id,
    DATE_TRUNC('month', timestamp) as usage_month,
    SUM(prompt_tokens) as prompt_tokens,
    SUM(completion_tokens) as completion_tokens,
    SUM(total_tokens) as total_tokens,
    SUM(estimated_cost_usd) as total_cost
FROM 
    token_usage_logs
GROUP BY 
    tenant_id, agent_id, DATE_TRUNC('month', timestamp)
ORDER BY 
    usage_month DESC;



    CREATE OR REPLACE VIEW model_token_usage_summary AS
SELECT 
    token_usage_logs.tenant_id,
    token_usage_logs.model_id,
    llm_models.name as model_name,
    llm_providers.name as provider_name,
    DATE_TRUNC('month', token_usage_logs.timestamp) as usage_month,
    SUM(token_usage_logs.prompt_tokens) as prompt_tokens,
    SUM(token_usage_logs.completion_tokens) as completion_tokens,
    SUM(token_usage_logs.total_tokens) as total_tokens,
    SUM(token_usage_logs.estimated_cost_usd) as total_cost
FROM 
    token_usage_logs
JOIN 
    llm_models ON token_usage_logs.model_id = llm_models.id
JOIN 
    llm_providers ON llm_models.provider_id = llm_providers.id
GROUP BY 
    token_usage_logs.tenant_id, 
    token_usage_logs.model_id, 
    llm_models.name,
    llm_providers.name,
    DATE_TRUNC('month', token_usage_logs.timestamp)
ORDER BY 
    usage_month DESC, total_tokens DESC;



---------------- OPICIONAL - NÃO EXECUTA AGORA -----------

-- Criar função para configurar particionamento de logs
CREATE OR REPLACE FUNCTION create_token_usage_log_partition()
RETURNS TRIGGER AS $$
DECLARE
    partition_date TEXT;
    partition_name TEXT;
BEGIN
    -- Formato: token_usage_logs_YYYY_MM
    partition_date := TO_CHAR(NEW.timestamp, 'YYYY_MM');
    partition_name := 'token_usage_logs_' || partition_date;
    
    -- Verificar se a partição existe, se não, criar
    IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname = partition_name) THEN
        EXECUTE 'CREATE TABLE ' || partition_name || 
                ' PARTITION OF token_usage_logs ' ||
                ' FOR VALUES FROM (''' || 
                DATE_TRUNC('month', NEW.timestamp)::TEXT || 
                ''') TO (''' || 
                (DATE_TRUNC('month', NEW.timestamp) + INTERVAL '1 month')::TEXT || 
                ''')';
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Implementar particionamento (remover tabela original primeiro)
CREATE TABLE token_usage_logs_partitioned (
    -- Mesmas colunas da tabela original
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id INTEGER NOT NULL,
    agent_id UUID NOT NULL,
    conversation_id VARCHAR,
    model_id INTEGER NOT NULL,
    prompt_tokens INTEGER NOT NULL,
    completion_tokens INTEGER NOT NULL,
    total_tokens INTEGER NOT NULL,
    estimated_cost_usd FLOAT DEFAULT 0.0,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) PARTITION BY RANGE (timestamp);

-- Aplicar trigger para particionamento automático
CREATE TRIGGER trg_token_usage_log_partition
BEFORE INSERT ON token_usage_logs_partitioned
FOR EACH ROW
EXECUTE FUNCTION create_token_usage_log_partition();