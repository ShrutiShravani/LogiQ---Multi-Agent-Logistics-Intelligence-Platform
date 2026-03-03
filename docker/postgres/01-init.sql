CREATE DATABASE LOGIQ;

--connect to database
\c logiq_db;

--create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

--create tables for agent state
CREATE TABLE IF NOT EXISTS agent_state(
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),,
    agent_name VARCHAR(100) NOT NULL,
    Session_id VARCHAR(100) NOT NULL,
    State_data JSONB NOT NULL,
    Created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    Updated_at TIMESTAMP DEFAULT CURRENT_TIMEST
);

CREATE TABLE IF NOT EXISTS conversations(
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id VARCHAR(100) NOT NULL,
    query TEXT NOT NULL,
    response TEXT,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_logs(
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trace_id VARCHAR(100) NOT NULL,
    agent_name VARCHAR(100) NOT NULL,
    action VARCHAR(200) NOT NULL,
    input_summary TEXT,
    output_summary TEXT,
    reasoning TEXT,
    model_version VARCHAR(50),
    fallback_used BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

);

--CREATE INdEXES

CREATE INDEX idx_agent_state_session ON agent_state(session_id);
CREATE INDEX idx_conversations_session ON conversations(session_id);
CREATE INDEX idx_audit_logs_trace ON audit_logs(trace_id);
CREATE INDEX idx_audit_logs_agent ON audit_logs(agent_name);
