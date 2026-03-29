-- DKB PostgreSQL Schema v0.1
-- Adjust vector dimensions if you choose a different embedding model.
-- Recommended extensions: pgcrypto, vector, pg_trgm

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE SCHEMA IF NOT EXISTS dkb;

-- =========================================================
-- SOURCES
-- =========================================================
CREATE TABLE IF NOT EXISTS dkb.source (
    source_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_kind TEXT NOT NULL CHECK (source_kind IN (
        'git_repo','local_folder','archive','manual_upload','web_page'
    )),
    origin_uri TEXT NOT NULL UNIQUE,
    owner_name TEXT,
    canonical_source_name TEXT,
    provenance_hint TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_source_kind ON dkb.source(source_kind);
CREATE INDEX IF NOT EXISTS idx_source_active ON dkb.source(is_active);
CREATE INDEX IF NOT EXISTS idx_source_metadata_gin ON dkb.source USING GIN(metadata);

-- =========================================================
-- SNAPSHOTS
-- =========================================================
CREATE TABLE IF NOT EXISTS dkb.source_snapshot (
    snapshot_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID NOT NULL REFERENCES dkb.source(source_id) ON DELETE CASCADE,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revision_ref TEXT,
    revision_type TEXT NOT NULL DEFAULT 'none' CHECK (revision_type IN (
        'commit','tag','branch','digest','manual_version','none'
    )),
    checksum TEXT,
    license_text TEXT,
    raw_blob_uri TEXT,
    capture_status TEXT NOT NULL DEFAULT 'captured' CHECK (capture_status IN (
        'captured','partial','failed'
    )),
    snapshot_meta JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (source_id, revision_ref, checksum)
);

CREATE INDEX IF NOT EXISTS idx_snapshot_source_id ON dkb.source_snapshot(source_id);
CREATE INDEX IF NOT EXISTS idx_snapshot_captured_at ON dkb.source_snapshot(captured_at DESC);
CREATE INDEX IF NOT EXISTS idx_snapshot_meta_gin ON dkb.source_snapshot USING GIN(snapshot_meta);

-- =========================================================
-- RAW DIRECTIVES
-- =========================================================
CREATE TABLE IF NOT EXISTS dkb.raw_directive (
    raw_directive_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_id UUID NOT NULL REFERENCES dkb.source_snapshot(snapshot_id) ON DELETE CASCADE,
    raw_name TEXT NOT NULL,
    entry_path TEXT,
    declared_type TEXT,
    content_format TEXT NOT NULL DEFAULT 'markdown' CHECK (content_format IN (
        'markdown','yaml','json','text','html','unknown'
    )),
    language_code TEXT DEFAULT 'en',
    summary_raw TEXT,
    body_raw TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    tsv tsvector GENERATED ALWAYS AS (
        to_tsvector(
            'simple',
            coalesce(raw_name,'') || ' ' ||
            coalesce(summary_raw,'') || ' ' ||
            coalesce(body_raw,'')
        )
    ) STORED
);

CREATE INDEX IF NOT EXISTS idx_raw_snapshot_id ON dkb.raw_directive(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_raw_declared_type ON dkb.raw_directive(declared_type);
CREATE INDEX IF NOT EXISTS idx_raw_entry_path_trgm ON dkb.raw_directive USING GIN(entry_path gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_raw_metadata_gin ON dkb.raw_directive USING GIN(metadata);
CREATE INDEX IF NOT EXISTS idx_raw_tsv_gin ON dkb.raw_directive USING GIN(tsv);

-- =========================================================
-- EVIDENCE
-- =========================================================
CREATE TABLE IF NOT EXISTS dkb.evidence (
    evidence_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    raw_directive_id UUID NOT NULL REFERENCES dkb.raw_directive(raw_directive_id) ON DELETE CASCADE,
    evidence_kind TEXT NOT NULL CHECK (evidence_kind IN (
        'summary','role_phrase','input_output','usage_example','license_excerpt',
        'install_note','tool_reference','source_signal','activity_signal','manual_note'
    )),
    excerpt TEXT NOT NULL,
    location_ref TEXT,
    weight_hint NUMERIC(4,3) DEFAULT 0.500 CHECK (weight_hint >= 0 AND weight_hint <= 1),
    evidence_meta JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_evidence_raw_directive_id ON dkb.evidence(raw_directive_id);
CREATE INDEX IF NOT EXISTS idx_evidence_kind ON dkb.evidence(evidence_kind);
CREATE INDEX IF NOT EXISTS idx_evidence_meta_gin ON dkb.evidence USING GIN(evidence_meta);

-- =========================================================
-- CANONICAL DIRECTIVES
-- =========================================================
CREATE TABLE IF NOT EXISTS dkb.canonical_directive (
    directive_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    preferred_name TEXT NOT NULL UNIQUE,
    normalized_summary TEXT,
    primary_human_label TEXT,
    scope TEXT NOT NULL DEFAULT 'global' CHECK (scope IN ('global','workspace','team','private')),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN (
        'active','draft','archived','deprecated'
    )),
    canonical_meta JSONB NOT NULL DEFAULT '{}'::jsonb,
    tsv tsvector GENERATED ALWAYS AS (
        to_tsvector(
            'simple',
            coalesce(preferred_name,'') || ' ' || coalesce(normalized_summary,'')
        )
    ) STORED
);

CREATE INDEX IF NOT EXISTS idx_canonical_status ON dkb.canonical_directive(status);
CREATE INDEX IF NOT EXISTS idx_canonical_scope ON dkb.canonical_directive(scope);
CREATE INDEX IF NOT EXISTS idx_canonical_meta_gin ON dkb.canonical_directive USING GIN(canonical_meta);
CREATE INDEX IF NOT EXISTS idx_canonical_tsv_gin ON dkb.canonical_directive USING GIN(tsv);

-- =========================================================
-- RAW TO CANONICAL MAPPING
-- =========================================================
CREATE TABLE IF NOT EXISTS dkb.raw_to_canonical_map (
    mapping_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    raw_directive_id UUID NOT NULL REFERENCES dkb.raw_directive(raw_directive_id) ON DELETE CASCADE,
    directive_id UUID NOT NULL REFERENCES dkb.canonical_directive(directive_id) ON DELETE CASCADE,
    mapping_score NUMERIC(5,4) NOT NULL CHECK (mapping_score >= 0 AND mapping_score <= 1),
    mapping_reason TEXT,
    mapping_status TEXT NOT NULL DEFAULT 'candidate' CHECK (mapping_status IN (
        'candidate','accepted','rejected','manual'
    )),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (raw_directive_id, directive_id)
);

CREATE INDEX IF NOT EXISTS idx_map_raw_directive_id ON dkb.raw_to_canonical_map(raw_directive_id);
CREATE INDEX IF NOT EXISTS idx_map_directive_id ON dkb.raw_to_canonical_map(directive_id);
CREATE INDEX IF NOT EXISTS idx_map_status ON dkb.raw_to_canonical_map(mapping_status);

-- =========================================================
-- DIMENSION MODEL
-- =========================================================
CREATE TABLE IF NOT EXISTS dkb.dimension_model (
    dimension_model_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_key TEXT NOT NULL UNIQUE,
    version TEXT NOT NULL,
    description TEXT,
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_active BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dimension_model_active ON dkb.dimension_model(is_active);
CREATE INDEX IF NOT EXISTS idx_dimension_model_config_gin ON dkb.dimension_model USING GIN(config);

-- =========================================================
-- DIMENSION SCORE
-- =========================================================
CREATE TABLE IF NOT EXISTS dkb.dimension_score (
    dimension_score_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    directive_id UUID NOT NULL REFERENCES dkb.canonical_directive(directive_id) ON DELETE CASCADE,
    dimension_model_id UUID NOT NULL REFERENCES dkb.dimension_model(dimension_model_id) ON DELETE CASCADE,
    dimension_group TEXT NOT NULL,
    dimension_key TEXT NOT NULL,
    score NUMERIC(6,5) NOT NULL CHECK (score >= 0 AND score <= 1),
    confidence NUMERIC(6,5) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    explanation TEXT,
    features JSONB NOT NULL DEFAULT '{}'::jsonb,
    scored_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (directive_id, dimension_model_id, dimension_group, dimension_key)
);

CREATE INDEX IF NOT EXISTS idx_score_directive_id ON dkb.dimension_score(directive_id);
CREATE INDEX IF NOT EXISTS idx_score_model_id ON dkb.dimension_score(dimension_model_id);
CREATE INDEX IF NOT EXISTS idx_score_group_key ON dkb.dimension_score(dimension_group, dimension_key);
CREATE INDEX IF NOT EXISTS idx_score_features_gin ON dkb.dimension_score USING GIN(features);

-- =========================================================
-- VERDICT
-- =========================================================
CREATE TABLE IF NOT EXISTS dkb.verdict (
    verdict_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    directive_id UUID NOT NULL REFERENCES dkb.canonical_directive(directive_id) ON DELETE CASCADE,
    dimension_model_id UUID NOT NULL REFERENCES dkb.dimension_model(dimension_model_id) ON DELETE CASCADE,
    provenance_state TEXT NOT NULL CHECK (provenance_state IN (
        'official','vendor','community','individual','unknown'
    )),
    trust_state TEXT NOT NULL CHECK (trust_state IN (
        'unknown','reviewing','verified','caution','blocked'
    )),
    legal_state TEXT NOT NULL CHECK (legal_state IN (
        'clear','custom','no_license','removed','restricted'
    )),
    lifecycle_state TEXT NOT NULL CHECK (lifecycle_state IN (
        'active','stale','dormant','archived','disappeared'
    )),
    recommendation_state TEXT NOT NULL CHECK (recommendation_state IN (
        'candidate','preferred','merged','excluded','deprecated'
    )),
    verdict_reason TEXT,
    policy_trace JSONB NOT NULL DEFAULT '{}'::jsonb,
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (directive_id, dimension_model_id)
);

CREATE INDEX IF NOT EXISTS idx_verdict_directive_id ON dkb.verdict(directive_id);
CREATE INDEX IF NOT EXISTS idx_verdict_model_id ON dkb.verdict(dimension_model_id);
CREATE INDEX IF NOT EXISTS idx_verdict_states ON dkb.verdict(
    trust_state, legal_state, lifecycle_state, recommendation_state
);
CREATE INDEX IF NOT EXISTS idx_verdict_policy_trace_gin ON dkb.verdict USING GIN(policy_trace);

-- =========================================================
-- RELATIONS
-- =========================================================
CREATE TABLE IF NOT EXISTS dkb.directive_relation (
    relation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    left_directive_id UUID NOT NULL REFERENCES dkb.canonical_directive(directive_id) ON DELETE CASCADE,
    relation_type TEXT NOT NULL CHECK (relation_type IN (
        'duplicate_of','variant_of','complements','conflicts_with','supersedes',
        'bundle_member_of','derived_from'
    )),
    right_directive_id UUID NOT NULL REFERENCES dkb.canonical_directive(directive_id) ON DELETE CASCADE,
    strength NUMERIC(6,5) DEFAULT 0.500 CHECK (strength >= 0 AND strength <= 1),
    explanation TEXT,
    relation_meta JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (left_directive_id, relation_type, right_directive_id),
    CHECK (left_directive_id <> right_directive_id)
);

CREATE INDEX IF NOT EXISTS idx_relation_left ON dkb.directive_relation(left_directive_id);
CREATE INDEX IF NOT EXISTS idx_relation_right ON dkb.directive_relation(right_directive_id);
CREATE INDEX IF NOT EXISTS idx_relation_type ON dkb.directive_relation(relation_type);
CREATE INDEX IF NOT EXISTS idx_relation_meta_gin ON dkb.directive_relation USING GIN(relation_meta);

-- =========================================================
-- PACKS
-- =========================================================
CREATE TABLE IF NOT EXISTS dkb.pack (
    pack_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pack_key TEXT NOT NULL UNIQUE,
    pack_name TEXT NOT NULL,
    pack_goal TEXT NOT NULL,
    pack_type TEXT NOT NULL CHECK (pack_type IN (
        'safe','lean','starter','role','experimental','custom'
    )),
    selection_policy JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft','active','deprecated'
    )),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pack_type ON dkb.pack(pack_type);
CREATE INDEX IF NOT EXISTS idx_pack_status ON dkb.pack(status);
CREATE INDEX IF NOT EXISTS idx_pack_policy_gin ON dkb.pack USING GIN(selection_policy);

CREATE TABLE IF NOT EXISTS dkb.pack_item (
    pack_item_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pack_id UUID NOT NULL REFERENCES dkb.pack(pack_id) ON DELETE CASCADE,
    directive_id UUID NOT NULL REFERENCES dkb.canonical_directive(directive_id) ON DELETE CASCADE,
    inclusion_reason TEXT,
    priority_weight NUMERIC(6,5) DEFAULT 0.500 CHECK (priority_weight >= 0 AND priority_weight <= 1),
    role_fit JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (pack_id, directive_id)
);

CREATE INDEX IF NOT EXISTS idx_pack_item_pack_id ON dkb.pack_item(pack_id);
CREATE INDEX IF NOT EXISTS idx_pack_item_directive_id ON dkb.pack_item(directive_id);
CREATE INDEX IF NOT EXISTS idx_pack_item_role_fit_gin ON dkb.pack_item USING GIN(role_fit);

-- =========================================================
-- EMBEDDINGS
-- =========================================================
CREATE TABLE IF NOT EXISTS dkb.directive_embedding (
    directive_embedding_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    directive_id UUID NOT NULL REFERENCES dkb.canonical_directive(directive_id) ON DELETE CASCADE,
    embedding_model TEXT NOT NULL,
    embedding_dimensions INTEGER NOT NULL DEFAULT 1536,
    embedding vector(1536) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (directive_id, embedding_model)
);

CREATE INDEX IF NOT EXISTS idx_directive_embedding_hnsw
ON dkb.directive_embedding USING hnsw (embedding vector_cosine_ops);

-- =========================================================
-- AUDIT
-- =========================================================
CREATE TABLE IF NOT EXISTS dkb.audit_event (
    audit_event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    object_kind TEXT NOT NULL,
    object_id UUID,
    action TEXT NOT NULL,
    actor TEXT DEFAULT 'system',
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_object ON dkb.audit_event(object_kind, object_id);
CREATE INDEX IF NOT EXISTS idx_audit_created_at ON dkb.audit_event(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_payload_gin ON dkb.audit_event USING GIN(payload);

-- =========================================================
-- VIEWS
-- =========================================================
CREATE OR REPLACE VIEW dkb.directive_overview AS
SELECT
    d.directive_id,
    d.preferred_name,
    d.normalized_summary,
    d.primary_human_label,
    d.scope,
    d.status,
    v.provenance_state,
    v.trust_state,
    v.legal_state,
    v.lifecycle_state,
    v.recommendation_state,
    v.evaluated_at
FROM dkb.canonical_directive d
LEFT JOIN dkb.verdict v
  ON v.directive_id = d.directive_id;
