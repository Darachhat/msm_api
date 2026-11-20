-- =============================================================================
-- Migration 007: Hybrid Web + Mobile Authentication & Security Tables
--   - Add token_version to data.user for immediate access-token revocation
--   - Extend data.refresh_token for opaque token rotation, reuse detection & device sessions
--   - Create track.auth_audit_log
-- =============================================================================

BEGIN;

-- 1. Add token_version to data."user" (incremented on logout-all / password change / reset)
ALTER TABLE IF EXISTS data."user"
    ADD COLUMN IF NOT EXISTS token_version integer NOT NULL DEFAULT 0;

-- 2. Extend data.refresh_token for opaque rotation, reuse detection & per-device metadata
ALTER TABLE IF EXISTS data.refresh_token
    ADD COLUMN IF NOT EXISTS family_id uuid NOT NULL DEFAULT gen_random_uuid(),
    ADD COLUMN IF NOT EXISTS token_hash varchar(128),
    ADD COLUMN IF NOT EXISTS replaced_by_jti varchar(100),
    ADD COLUMN IF NOT EXISTS device_id varchar(255),
    ADD COLUMN IF NOT EXISTS device_name varchar(255),
    ADD COLUMN IF NOT EXISTS platform varchar(50),
    ADD COLUMN IF NOT EXISTS ip_address varchar(100),
    ADD COLUMN IF NOT EXISTS user_agent text,
    ADD COLUMN IF NOT EXISTS last_used_datetime timestamp without time zone,
    ADD COLUMN IF NOT EXISTS revoked_datetime timestamp without time zone,
    ADD COLUMN IF NOT EXISTS revoke_reason varchar(100);

CREATE UNIQUE INDEX IF NOT EXISTS uq_refresh_token_token_hash
    ON data.refresh_token (token_hash)
    WHERE token_hash IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_refresh_token_user_revoked
    ON data.refresh_token (user_id, revoked);

CREATE INDEX IF NOT EXISTS ix_refresh_token_family_id
    ON data.refresh_token (family_id);

-- 3. track.auth_audit_log (audit trail for all authentication events)
CREATE TABLE IF NOT EXISTS track.auth_audit_log (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    user_id uuid REFERENCES data."user"(id) ON DELETE SET NULL,
    username varchar(100),
    event_type varchar(50) NOT NULL,
    event_status varchar(20) NOT NULL,
    ip_address varchar(100),
    user_agent text,
    detail text,
    metadata_json jsonb,
    status_code varchar(20) NOT NULL DEFAULT 'ACTIVE',
    created_datetime timestamp without time zone NOT NULL DEFAULT now(),
    updated_datetime timestamp without time zone,
    deleted_datetime timestamp without time zone,
    created_by varchar(100),
    updated_by varchar(100),
    deleted_by varchar(100),
    CONSTRAINT auth_audit_log_pkey PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS ix_auth_audit_log_user_created
    ON track.auth_audit_log (user_id, created_datetime DESC);

CREATE INDEX IF NOT EXISTS ix_auth_audit_log_event_type
    ON track.auth_audit_log (event_type, created_datetime DESC);

COMMIT;
