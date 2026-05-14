
CREATE EXTENSION IF NOT EXISTS vector;


CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    bot_id INTEGER NOT NULL,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    organization VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(bot_id, email)
);

CREATE INDEX idx_users_bot_email ON users(bot_id, email);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_organization ON users(organization);


CREATE TABLE IF NOT EXISTS sessions (
    id SERIAL PRIMARY KEY,
    bot_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_sessions_session_id ON sessions(session_id);
CREATE INDEX idx_sessions_user_id ON sessions(user_id);
CREATE INDEX idx_sessions_bot_id ON sessions(bot_id);

-- ============================================================
-- CONVERSATIONS TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS conversations (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    bot_id INTEGER NOT NULL,
    status VARCHAR(50) DEFAULT 'active' CHECK (status IN ('active', 'closed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_conversations_user_bot ON conversations(user_id, bot_id);
CREATE INDEX idx_conversations_status ON conversations(status);
CREATE INDEX idx_conversations_updated ON conversations(updated_at DESC);

-- ============================================================
-- MESSAGES TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    category VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_messages_conversation ON messages(conversation_id);
CREATE INDEX idx_messages_created ON messages(created_at DESC);
CREATE INDEX idx_messages_role ON messages(role);

-- ============================================================
-- KB_FILES TABLE (Knowledge Base Files)
-- ============================================================
CREATE TABLE IF NOT EXISTS kb_files (
    id SERIAL PRIMARY KEY,
    file_name VARCHAR(500) NOT NULL,
    file_hash VARCHAR(64) NOT NULL,
    bot_id INTEGER NOT NULL,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(file_hash, bot_id)
);

CREATE INDEX idx_kb_files_bot_id ON kb_files(bot_id);
CREATE INDEX idx_kb_files_hash ON kb_files(file_hash);

-- ============================================================
-- KB_CHUNKS TABLE (Knowledge Base Chunks with Embeddings)
-- ============================================================
CREATE TABLE IF NOT EXISTS kb_chunks (
    id SERIAL PRIMARY KEY,
    chunk_text TEXT NOT NULL,
    chunk_hash VARCHAR(64) NOT NULL,
    embedding vector(384),  -- Dimension for sentence-transformers/all-MiniLM-L6-v2
    kb_file_id INTEGER NOT NULL REFERENCES kb_files(id) ON DELETE CASCADE,
    bot_id INTEGER NOT NULL,
    category VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(chunk_hash, bot_id)
);

CREATE INDEX idx_kb_chunks_bot_id ON kb_chunks(bot_id);
CREATE INDEX idx_kb_chunks_file_id ON kb_chunks(kb_file_id);
CREATE INDEX idx_kb_chunks_category ON kb_chunks(category);

-- Create vector similarity index for fast retrieval
CREATE INDEX idx_kb_chunks_embedding ON kb_chunks USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- ============================================================
-- RATE_LIMITING TABLE (for ticket creation)
-- ============================================================
CREATE TABLE IF NOT EXISTS rate_limits (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    action VARCHAR(100) NOT NULL,
    count INTEGER DEFAULT 1,
    window_start TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(email, action)
);

CREATE INDEX idx_rate_limits_email_action ON rate_limits(email, action);
CREATE INDEX idx_rate_limits_window ON rate_limits(window_start);

-- ============================================================
-- BOT_CONFIGS TABLE (for multi-bot support)
-- ============================================================
CREATE TABLE IF NOT EXISTS bot_configs (
    id SERIAL PRIMARY KEY,
    bot_id INTEGER UNIQUE NOT NULL,
    ingest_config JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_bot_configs_bot_id ON bot_configs(bot_id);

-- ============================================================
-- AUDIT_LOG TABLE (for security tracking)
-- ============================================================
CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(100),
    resource_id INTEGER,
    details JSONB,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_log_user ON audit_log(user_id);
CREATE INDEX idx_audit_log_action ON audit_log(action);
CREATE INDEX idx_audit_log_created ON audit_log(created_at DESC);

-- ============================================================
-- FUNCTIONS & TRIGGERS
-- ============================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger for users table
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Trigger for conversations table
CREATE TRIGGER update_conversations_updated_at BEFORE UPDATE ON conversations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- INITIAL DATA
-- ============================================================

-- Insert default bot configuration
INSERT INTO bot_configs (bot_id, ingest_config)
VALUES (
    1,
    '{
        "bot_name": "MPS Support Bot",
        "require_registration": true,
        "initial_message": "Please provide your name and email.",
        "domain_message": "I can only answer domain-related questions.",
        "escalation_message": "No relevant information found.",
        "memory_limit": 6,
        "llm_config": {
            "repo_id": "llama-3.1-8b-instant",
            "temperature": 0.0,
            "max_new_tokens": 2048
        },
        "retriever_config": {
            "top_k": 15,
            "domain_threshold": 0.65
        },
        "chunk_size": 500,
        "chunk_overlap": 50
    }'::jsonb
)
ON CONFLICT (bot_id) DO NOTHING;

-- ============================================================
-- CLEANUP FUNCTION (for old sessions)
-- ============================================================

CREATE OR REPLACE FUNCTION cleanup_old_sessions()
RETURNS void AS $$
BEGIN
    DELETE FROM sessions WHERE last_activity < NOW() - INTERVAL '30 days';
    DELETE FROM rate_limits WHERE window_start < NOW() - INTERVAL '1 day';
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- GRANTS (adjust as needed for your user)
-- ============================================================

-- Grant permissions to your database user
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO your_db_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO your_db_user;

-- ============================================================
-- NOTES
-- ============================================================

-- To initialize the database, run:
-- psql -U postgres -d HIGHWIRE_BOT_DATABASE -f schema.sql

-- To reset the database (WARNING: deletes all data):
-- DROP SCHEMA public CASCADE;
-- CREATE SCHEMA public;
-- Then run this file again

-- To backup:
-- pg_dump -U postgres HIGHWIRE_BOT_DATABASE > backup.sql

-- To restore:
-- psql -U postgres HIGHWIRE_BOT_DATABASE < backup.sql
