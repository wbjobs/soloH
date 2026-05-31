-- 比特币交易图分析系统 - 数据库初始化DDL

-- 启用扩展
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS btree_gist;

-- 区块表
CREATE TABLE blocks (
    block_height INTEGER PRIMARY KEY,
    block_time TIMESTAMPTZ NOT NULL,
    block_hash VARCHAR(64) UNIQUE NOT NULL,
    tx_count INTEGER NOT NULL DEFAULT 0,
    total_btc NUMERIC(28, 8) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_blocks_time ON blocks(block_time DESC);
CREATE INDEX idx_blocks_hash ON blocks(block_hash);

-- 交易表 (使用 TimescaleDB 分区)
CREATE TABLE transactions (
    txid VARCHAR(64) PRIMARY KEY,
    block_height INTEGER NOT NULL REFERENCES blocks(block_height) ON DELETE CASCADE,
    block_time TIMESTAMPTZ NOT NULL,
    total_input NUMERIC(28, 8) NOT NULL DEFAULT 0,
    total_output NUMERIC(28, 8) NOT NULL DEFAULT 0,
    fee NUMERIC(28, 8) NOT NULL DEFAULT 0,
    input_count INTEGER NOT NULL DEFAULT 0,
    output_count INTEGER NOT NULL DEFAULT 0,
    is_coinbase BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 创建 TimescaleDB 超表
SELECT create_hypertable('transactions', 'block_time');

CREATE INDEX idx_transactions_block ON transactions(block_height);
CREATE INDEX idx_transactions_time ON transactions(block_time DESC);

-- 交易输入表
CREATE TABLE tx_inputs (
    id BIGSERIAL PRIMARY KEY,
    txid VARCHAR(64) NOT NULL REFERENCES transactions(txid) ON DELETE CASCADE,
    vout INTEGER NOT NULL,
    prev_txid VARCHAR(64),
    prev_vout INTEGER,
    address VARCHAR NOT NULL,
    value NUMERIC(28, 8) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_tx_inputs_txid ON tx_inputs(txid);
CREATE INDEX idx_tx_inputs_address ON tx_inputs(address);
CREATE INDEX idx_tx_inputs_prev ON tx_inputs(prev_txid, prev_vout);
CREATE INDEX idx_tx_inputs_value ON tx_inputs(value DESC);

-- 交易输出表
CREATE TABLE tx_outputs (
    id BIGSERIAL PRIMARY KEY,
    txid VARCHAR(64) NOT NULL REFERENCES transactions(txid) ON DELETE CASCADE,
    vout INTEGER NOT NULL,
    address VARCHAR NOT NULL,
    value NUMERIC(28, 8) NOT NULL,
    script_type VARCHAR(50),
    is_spent BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_tx_outputs_txid ON tx_outputs(txid);
CREATE INDEX idx_tx_outputs_address ON tx_outputs(address);
CREATE INDEX idx_tx_outputs_unspent ON tx_outputs(address, is_spent) WHERE is_spent = FALSE;
CREATE INDEX idx_tx_outputs_value ON tx_outputs(value DESC);

-- 地址表
CREATE TABLE addresses (
    address VARCHAR PRIMARY KEY,
    first_seen TIMESTAMPTZ,
    last_seen TIMESTAMPTZ,
    total_received NUMERIC(28, 8) NOT NULL DEFAULT 0,
    total_sent NUMERIC(28, 8) NOT NULL DEFAULT 0,
    balance NUMERIC(28, 8) NOT NULL DEFAULT 0,
    tx_count INTEGER NOT NULL DEFAULT 0,
    cluster_id VARCHAR(36),
    suspicious_score NUMERIC(5, 2),
    risk_factors JSONB,
    risk_level VARCHAR(20),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_addresses_cluster ON addresses(cluster_id);
CREATE INDEX idx_addresses_risk ON addresses(suspicious_score DESC NULLS LAST);
CREATE INDEX idx_addresses_balance ON addresses(balance DESC);
CREATE INDEX idx_addresses_tx_count ON addresses(tx_count DESC);

-- 地址聚类表
CREATE TABLE address_clusters (
    cluster_id VARCHAR(36) PRIMARY KEY,
    heuristic VARCHAR(50) NOT NULL,
    confidence NUMERIC(5, 4) NOT NULL,
    size INTEGER NOT NULL DEFAULT 0,
    total_value NUMERIC(28, 8) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_clusters_heuristic ON address_clusters(heuristic);
CREATE INDEX idx_clusters_size ON address_clusters(size DESC);
CREATE INDEX idx_clusters_value ON address_clusters(total_value DESC);

-- 地址聚类成员表
CREATE TABLE cluster_members (
    cluster_id VARCHAR(36) NOT NULL REFERENCES address_clusters(cluster_id) ON DELETE CASCADE,
    address VARCHAR NOT NULL REFERENCES addresses(address) ON DELETE CASCADE,
    joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (cluster_id, address)
);

CREATE INDEX idx_cluster_members_address ON cluster_members(address);
CREATE INDEX idx_cluster_members_joined ON cluster_members(joined_at DESC);

-- 可疑模式表
CREATE TABLE suspicious_patterns (
    id BIGSERIAL PRIMARY KEY,
    pattern_type VARCHAR(50) NOT NULL,
    confidence NUMERIC(5, 4) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    description TEXT,
    evidence JSONB,
    address VARCHAR REFERENCES addresses(address) ON DELETE CASCADE,
    txid VARCHAR(64) REFERENCES transactions(txid) ON DELETE CASCADE,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_patterns_type ON suspicious_patterns(pattern_type);
CREATE INDEX idx_patterns_address ON suspicious_patterns(address);
CREATE INDEX idx_patterns_severity ON suspicious_patterns(severity);
CREATE INDEX idx_patterns_detected ON suspicious_patterns(detected_at DESC);
CREATE INDEX idx_patterns_confidence ON suspicious_patterns(confidence DESC);

-- 任务表
CREATE TABLE tasks (
    task_id VARCHAR(36) PRIMARY KEY,
    task_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    progress NUMERIC(5, 2) NOT NULL DEFAULT 0,
    error_message TEXT,
    result JSONB,
    params JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

CREATE INDEX idx_tasks_type ON tasks(task_type);
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_created ON tasks(created_at DESC);

-- 任务日志表
CREATE TABLE task_logs (
    id BIGSERIAL PRIMARY KEY,
    task_id VARCHAR(36) NOT NULL REFERENCES tasks(task_id) ON DELETE CASCADE,
    log_level VARCHAR(20) NOT NULL,
    message TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_task_logs_task ON task_logs(task_id);
CREATE INDEX idx_task_logs_level ON task_logs(log_level);
CREATE INDEX idx_task_logs_created ON task_logs(created_at DESC);

-- 图边表 (用于高效图查询)
CREATE TABLE graph_edges (
    id BIGSERIAL PRIMARY KEY,
    from_address VARCHAR NOT NULL REFERENCES addresses(address) ON DELETE CASCADE,
    to_address VARCHAR NOT NULL REFERENCES addresses(address) ON DELETE CASCADE,
    txid VARCHAR(64) NOT NULL REFERENCES transactions(txid) ON DELETE CASCADE,
    value NUMERIC(28, 8) NOT NULL,
    block_time TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

SELECT create_hypertable('graph_edges', 'block_time');

CREATE INDEX idx_edges_from ON graph_edges(from_address);
CREATE INDEX idx_edges_to ON graph_edges(to_address);
CREATE INDEX idx_edges_value ON graph_edges(value DESC);
CREATE INDEX idx_edges_time ON graph_edges(block_time DESC);
CREATE INDEX idx_edges_address_pair ON graph_edges(from_address, to_address);
