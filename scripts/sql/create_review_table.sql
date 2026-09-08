-- Tabla de revisión HITL para el caso partner-fill (destino escribible: n8n_odoo)
CREATE TABLE IF NOT EXISTS hermes_partner_fill (
    id SERIAL PRIMARY KEY,
    call_id INTEGER NOT NULL UNIQUE,
    partner_id INTEGER NOT NULL,
    duration_seconds NUMERIC,
    create_date TIMESTAMP,
    schema_version VARCHAR(20) DEFAULT 'partner_fill_0.2.0',
    missing_fields JSONB NOT NULL DEFAULT '[]',
    extracted_data JSONB NOT NULL DEFAULT '{}',
    evidence JSONB NOT NULL DEFAULT '{}',
    consensus_status VARCHAR(12) NOT NULL DEFAULT 'pending', -- auto_ok|review|not_found|single_model
    validators_passed JSONB NOT NULL DEFAULT '{}',
    review_status VARCHAR(12) NOT NULL DEFAULT 'pending',    -- pending|approved|rejected|applied
    reviewed_by VARCHAR(80),
    reviewed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_pf_review ON hermes_partner_fill (review_status, consensus_status);