-- =============================================================================
-- Migration 011: Migrate User, RBAC, and Audit tables out of auth schema
--   - Move auth.role, auth.service_module, auth.role_permission -> base_data
--   - Move auth."user", auth.refresh_token -> data
--   - Move auth.auth_audit_log -> track
--   - Drop redundant auth.login_history
-- =============================================================================

BEGIN;

-- 1. Move reference RBAC tables from auth to base_data (if they still exist in auth)
ALTER TABLE IF EXISTS auth.role            SET SCHEMA base_data;
ALTER TABLE IF EXISTS auth.service_module  SET SCHEMA base_data;
ALTER TABLE IF EXISTS auth.role_permission SET SCHEMA base_data;

-- 2. Move user & token tables from auth to data (if they still exist in auth)
ALTER TABLE IF EXISTS auth."user"               SET SCHEMA data;
ALTER TABLE IF EXISTS auth.refresh_token        SET SCHEMA data;

-- 3. Move authentication audit log from auth to track (if it still exists in auth)
ALTER TABLE IF EXISTS auth.auth_audit_log SET SCHEMA track;

-- 4. Drop redundant auth.login_history table
DROP TABLE IF EXISTS auth.login_history;

-- 5. Drop password reset tokens (admin-set passwords only)
DROP TABLE IF EXISTS auth.password_reset_token;
DROP TABLE IF EXISTS data.password_reset_token;

COMMIT;
