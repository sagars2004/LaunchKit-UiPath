-- LaunchKit Supabase Schema
-- Apply via Supabase SQL Editor or: supabase db push

-- Extensions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ── Enums ────────────────────────────────────────────────────────────────────

CREATE TYPE run_status AS ENUM (
    'intake',
    'intelligence',
    'analyzing',
    'generating',
    'scoring',
    'reviewing',
    'publishing',
    'monitoring',
    'complete',
    'failed'
);

CREATE TYPE artifact_type AS ENUM (
    'readme',
    'devpost_copy',
    'demo_script',
    'social_content',
    'blog_draft'
);

CREATE TYPE artifact_status AS ENUM (
    'pending',
    'generated',
    'scored',
    'approved',
    'rejected',
    'published'
);

-- ── runs ───────────────────────────────────────────────────────────────────

CREATE TABLE runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    status          run_status NOT NULL DEFAULT 'intake',
    intake          JSONB NOT NULL DEFAULT '{}',
    hackathon_brief JSONB,
    winner_patterns JSONB,
    winning_brief   JSONB,
    repo_context    JSONB,
    code_intelligence JSONB,
    quality_report  JSONB,
    publishing_results JSONB DEFAULT '{}',
    analytics       JSONB DEFAULT '{}',
    error_message   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_runs_status ON runs(status);
CREATE INDEX idx_runs_created_at ON runs(created_at DESC);

-- ── artifacts ────────────────────────────────────────────────────────────────

CREATE TABLE artifacts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id          UUID NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    artifact_type   artifact_type NOT NULL,
    status          artifact_status NOT NULL DEFAULT 'pending',
    content         TEXT,
    quality_score   REAL,
    quality_feedback TEXT,
    published_url   TEXT,
    revision_count  INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (run_id, artifact_type)
);

CREATE INDEX idx_artifacts_run_id ON artifacts(run_id);
CREATE INDEX idx_artifacts_status ON artifacts(status);

-- ── revisions ──────────────────────────────────────────────────────────────────

CREATE TABLE revisions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id          UUID NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    artifact_type   artifact_type NOT NULL,
    feedback        TEXT NOT NULL,
    previous_content TEXT,
    new_content     TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_revisions_run_id ON revisions(run_id);
CREATE INDEX idx_revisions_artifact ON revisions(run_id, artifact_type);

-- ── metrics ──────────────────────────────────────────────────────────────────

CREATE TABLE metrics (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id          UUID NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    source          TEXT NOT NULL,
    metric_type     TEXT NOT NULL,
    value           INTEGER NOT NULL,
    delta           INTEGER,
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_metrics_run_id ON metrics(run_id);
CREATE INDEX idx_metrics_recorded_at ON metrics(run_id, recorded_at DESC);

-- ── retrospectives ─────────────────────────────────────────────────────────────

CREATE TABLE retrospectives (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id          UUID NOT NULL UNIQUE REFERENCES runs(id) ON DELETE CASCADE,
    content         TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_retrospectives_run_id ON retrospectives(run_id);

-- ── Grants (required — Supabase API uses service_role key) ───────────────────
-- Without these, PostgREST returns: permission denied for table runs (42501)

GRANT USAGE ON SCHEMA public TO postgres, anon, authenticated, service_role;

GRANT ALL ON TABLE runs TO service_role;
GRANT ALL ON TABLE artifacts TO service_role;
GRANT ALL ON TABLE revisions TO service_role;
GRANT ALL ON TABLE metrics TO service_role;
GRANT ALL ON TABLE retrospectives TO service_role;

GRANT ALL ON TABLE runs TO authenticated;
GRANT ALL ON TABLE artifacts TO authenticated;
GRANT ALL ON TABLE revisions TO authenticated;
GRANT ALL ON TABLE metrics TO authenticated;
GRANT ALL ON TABLE retrospectives TO authenticated;

GRANT SELECT ON TABLE runs TO anon;
GRANT SELECT ON TABLE artifacts TO anon;
GRANT SELECT ON TABLE metrics TO anon;
GRANT SELECT ON TABLE retrospectives TO anon;

GRANT USAGE ON TYPE run_status TO service_role, authenticated, anon;
GRANT USAGE ON TYPE artifact_type TO service_role, authenticated, anon;
GRANT USAGE ON TYPE artifact_status TO service_role, authenticated, anon;

-- ── updated_at trigger ───────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER runs_updated_at
    BEFORE UPDATE ON runs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER artifacts_updated_at
    BEFORE UPDATE ON artifacts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER retrospectives_updated_at
    BEFORE UPDATE ON retrospectives
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ── Row Level Security ───────────────────────────────────────────────────────

ALTER TABLE runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE artifacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE revisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE retrospectives ENABLE ROW LEVEL SECURITY;

-- Service role bypasses RLS automatically when using service key.

-- Anon: read-only on non-sensitive tables (no revisions content in prod — adjust as needed)
CREATE POLICY anon_read_runs ON runs
    FOR SELECT TO anon USING (true);

CREATE POLICY anon_read_artifacts ON artifacts
    FOR SELECT TO anon USING (true);

CREATE POLICY anon_read_metrics ON metrics
    FOR SELECT TO anon USING (true);

CREATE POLICY anon_read_retrospectives ON retrospectives
    FOR SELECT TO anon USING (true);

-- Authenticated users: full access via service role only (backend uses service key)
CREATE POLICY service_all_runs ON runs
    FOR ALL TO authenticated USING (true) WITH CHECK (true);

CREATE POLICY service_all_artifacts ON artifacts
    FOR ALL TO authenticated USING (true) WITH CHECK (true);

CREATE POLICY service_all_revisions ON revisions
    FOR ALL TO authenticated USING (true) WITH CHECK (true);

CREATE POLICY service_all_metrics ON metrics
    FOR ALL TO authenticated USING (true) WITH CHECK (true);

CREATE POLICY service_all_retrospectives ON retrospectives
    FOR ALL TO authenticated USING (true) WITH CHECK (true);
