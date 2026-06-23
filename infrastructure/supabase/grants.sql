-- Quick fix: run this in Supabase SQL Editor if you get
-- "permission denied for table runs" (error 42501)
--
-- Your tables already exist — this only adds missing grants.

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
