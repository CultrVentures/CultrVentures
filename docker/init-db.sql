-- ═══════════════════════════════════════════════════════════════════
-- CULTR Ventures — Database Initialization
-- PostgreSQL 16 + pgvector
-- Run once on fresh database setup
-- ═══════════════════════════════════════════════════════════════════

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";        -- pgvector for embeddings

-- ── Users & Auth ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email       VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role        VARCHAR(50) NOT NULL DEFAULT 'user',  -- admin | operator | consultant | user
    full_name   VARCHAR(255),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login  TIMESTAMPTZ
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role);

-- ── Clients ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS clients (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        VARCHAR(255) NOT NULL,
    company     VARCHAR(255) NOT NULL,
    email       VARCHAR(255),
    tier        VARCHAR(50) NOT NULL DEFAULT 'starter',  -- starter | growth | enterprise
    industry    VARCHAR(100),
    owner_id    UUID REFERENCES users(id),
    metadata    JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_clients_tier ON clients(tier);
CREATE INDEX idx_clients_owner ON clients(owner_id);

-- ── Agents ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS agents (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id    VARCHAR(100) UNIQUE NOT NULL,  -- e.g., "mkt-content-strategist"
    department  VARCHAR(100) NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    status      VARCHAR(50) NOT NULL DEFAULT 'idle',  -- idle | running | error | paused
    skills      TEXT[] DEFAULT '{}',
    config      JSONB DEFAULT '{}',
    last_active TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_agents_department ON agents(department);
CREATE INDEX idx_agents_status ON agents(status);

-- ── Agent Tasks ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS agent_tasks (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id    VARCHAR(100) REFERENCES agents(agent_id),
    client_id   UUID REFERENCES clients(id),
    task_type   VARCHAR(100) NOT NULL,
    input_data  JSONB NOT NULL,
    output_data JSONB,
    status      VARCHAR(50) NOT NULL DEFAULT 'queued',  -- queued | running | completed | failed | hitl_pending
    priority    VARCHAR(20) NOT NULL DEFAULT 'normal',   -- low | normal | high | critical
    grounding_status VARCHAR(50),  -- verified | partial | unverified
    confidence  FLOAT,
    error       TEXT,
    started_at  TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_tasks_agent ON agent_tasks(agent_id);
CREATE INDEX idx_tasks_client ON agent_tasks(client_id);
CREATE INDEX idx_tasks_status ON agent_tasks(status);
CREATE INDEX idx_tasks_created ON agent_tasks(created_at DESC);

-- ── Knowledge Embeddings ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_path VARCHAR(500) NOT NULL,  -- vault path: memory/clients/acme/profile.md
    chunk_text  TEXT NOT NULL,
    embedding   vector(1024),  -- BGE-large-en-v1.5 dimension
    metadata    JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_chunks_source ON knowledge_chunks(source_path);
CREATE INDEX idx_chunks_embedding ON knowledge_chunks USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- ── ACP Transactions ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS acp_transactions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    offering_id     VARCHAR(255) NOT NULL,
    client_id       UUID REFERENCES clients(id),
    payment_method  VARCHAR(50) NOT NULL,  -- stripe | virtuals_acp
    amount_cents    INTEGER,
    currency        VARCHAR(10) DEFAULT 'usd',
    stripe_payment_id VARCHAR(255),
    onchain_tx_hash VARCHAR(255),
    status          VARCHAR(50) NOT NULL DEFAULT 'pending',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_acp_client ON acp_transactions(client_id);
CREATE INDEX idx_acp_status ON acp_transactions(status);

-- ── Grounding Audit Log ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS grounding_log (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_id         UUID REFERENCES agent_tasks(id),
    agent_id        VARCHAR(100),
    validation_stage VARCHAR(50) NOT NULL,  -- schema | source | freshness | contradiction | confidence | hitl
    passed          BOOLEAN NOT NULL,
    details         JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_grounding_task ON grounding_log(task_id);
CREATE INDEX idx_grounding_agent ON grounding_log(agent_id);

-- ── Row-Level Security ─────────────────────────────────────────────
-- Enable RLS on client-scoped tables
ALTER TABLE clients ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE acp_transactions ENABLE ROW LEVEL SECURITY;

-- Admin sees everything
CREATE POLICY admin_all_clients ON clients FOR ALL TO cultr
    USING (
        current_setting('app.user_role', true) = 'admin'
    );

-- Users see only their assigned clients
CREATE POLICY user_own_clients ON clients FOR SELECT TO cultr
    USING (
        owner_id::text = current_setting('app.user_id', true)
    );

-- ── Seed admin user ────────────────────────────────────────────────
INSERT INTO users (email, password_hash, role, full_name)
VALUES (
    'ketchel.david@gmail.com',
    crypt('CHANGE_ME_ON_FIRST_LOGIN', gen_salt('bf')),
    'admin',
    'Dave Ketchel'
) ON CONFLICT (email) DO NOTHING;

-- Done
SELECT 'CULTR Platform database initialized successfully' AS status;
