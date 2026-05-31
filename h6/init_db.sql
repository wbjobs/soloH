CREATE DATABASE rna_db;

\c rna_db;

CREATE TABLE IF NOT EXISTS rna_families (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    pattern VARCHAR(500) NOT NULL,
    must_pair JSONB,
    must_unpair JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO rna_families (name, pattern, must_pair, must_unpair) VALUES
('tRNA-like', 'AUGC[AUGC]{30,60}AUGC', '[[0, 3], [4, 7]]', '[1, 2, 5, 6]'),
('Stem-loop', '[GC]{4,}[AUGC]{3,}[GC]{4,}', '[]', '[]'),
('miRNA', '[AUGC]{21,23}', '[]', '[]')
ON CONFLICT (name) DO NOTHING;
