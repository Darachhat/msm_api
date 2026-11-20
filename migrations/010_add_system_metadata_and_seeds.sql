-- =============================================================================
-- Migration 010: Add metadata_json to auth.system & seed external systems
--                (CLOUDFLARE_R2) for DB-managed outbound config
-- =============================================================================

BEGIN;

ALTER TABLE IF EXISTS auth.system
    ADD COLUMN IF NOT EXISTS metadata_json jsonb;

INSERT INTO auth.system (code, name, description, scope, metadata_json) VALUES
    (
        'CLOUDFLARE_R2',
        'Cloudflare R2 Object Storage',
        'S3-compatible object storage for generated Excel reports and signatures',
        'EXTERNAL',
        '{"bucket_name": "medicine-stock-reports", "region": "auto", "presigned_expire_seconds": 3600}'::jsonb
    )
ON CONFLICT (code) DO NOTHING;

COMMIT;
