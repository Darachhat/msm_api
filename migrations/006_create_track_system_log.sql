-- =============================================================================
-- Migration 006: Create track schema and track.system_log table
--                (Inbound & Outbound API audit logging)
-- =============================================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS track;

CREATE TABLE IF NOT EXISTS track.system_log (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    client_log_id varchar(40),
    traffic_type varchar(20),
    system_code varchar(100),
    channel varchar(50),
    request_method varchar(10) NOT NULL,
    request_endpoint text NOT NULL,
    request_netloc varchar(255),
    request_content_type varchar(255),
    request_user_agent text,
    request_headers jsonb,
    request_body jsonb,
    requested_datetime timestamp without time zone,
    client_ip varchar(50),
    response_code integer,
    response_headers jsonb,
    response_body jsonb,
    response_duration numeric,
    response_datetime timestamp without time zone,
    status_code varchar(20) NOT NULL DEFAULT 'ACTIVE',
    created_datetime timestamp without time zone NOT NULL DEFAULT now(),
    updated_datetime timestamp without time zone,
    deleted_datetime timestamp without time zone,
    created_by varchar(100),
    updated_by varchar(100),
    deleted_by varchar(100),
    CONSTRAINT system_log_pkey PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS ix_system_log_traffic_created
    ON track.system_log (traffic_type, created_datetime DESC);

CREATE INDEX IF NOT EXISTS ix_system_log_client_log_id
    ON track.system_log (client_log_id);

CREATE INDEX IF NOT EXISTS ix_system_log_system_code
    ON track.system_log (system_code);

CREATE INDEX IF NOT EXISTS ix_system_log_response_code
    ON track.system_log (response_code);

COMMIT;
