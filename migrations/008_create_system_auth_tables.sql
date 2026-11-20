-- =============================================================================
-- Migration 008: System-to-System Authentication Tables (following hub_api)
--   - auth.system
--   - auth.system_credential
--   - auth.credential_api_key
--   - auth.credential_bearer
--   - auth.credential_basic
-- =============================================================================

BEGIN;

-- 1. auth.system
CREATE TABLE IF NOT EXISTS auth.system (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    code varchar(100) NOT NULL,
    name varchar(255) NOT NULL,
    description text,
    base_url varchar(500),
    scope varchar(50) NOT NULL DEFAULT 'INTERNAL',
    status_code varchar(20) NOT NULL DEFAULT 'ACTIVE',
    created_datetime timestamp without time zone NOT NULL DEFAULT now(),
    updated_datetime timestamp without time zone,
    deleted_datetime timestamp without time zone,
    created_by varchar(100),
    updated_by varchar(100),
    deleted_by varchar(100),
    CONSTRAINT system_pkey PRIMARY KEY (id),
    CONSTRAINT system_code_key UNIQUE (code)
);

-- 2. auth.system_credential
CREATE TABLE IF NOT EXISTS auth.system_credential (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    system_code varchar(100) NOT NULL REFERENCES auth.system(code) ON DELETE CASCADE,
    traffic_type varchar(20) NOT NULL,
    auth_type_code varchar(50) NOT NULL,
    description text,
    status_code varchar(20) NOT NULL DEFAULT 'ACTIVE',
    created_datetime timestamp without time zone NOT NULL DEFAULT now(),
    updated_datetime timestamp without time zone,
    deleted_datetime timestamp without time zone,
    created_by varchar(100),
    updated_by varchar(100),
    deleted_by varchar(100),
    CONSTRAINT system_credential_pkey PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS ix_system_credential_lookup
    ON auth.system_credential (system_code, traffic_type, auth_type_code);

-- 3. auth.credential_api_key
CREATE TABLE IF NOT EXISTS auth.credential_api_key (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    system_code varchar(100) NOT NULL REFERENCES auth.system(code) ON DELETE CASCADE,
    traffic_type varchar(20) NOT NULL,
    key_location varchar(20) NOT NULL DEFAULT 'header',
    key_name varchar(100) NOT NULL DEFAULT 'X-API-Key',
    key_value text NOT NULL,
    description text,
    status_code varchar(20) NOT NULL DEFAULT 'ACTIVE',
    created_datetime timestamp without time zone NOT NULL DEFAULT now(),
    updated_datetime timestamp without time zone,
    deleted_datetime timestamp without time zone,
    created_by varchar(100),
    updated_by varchar(100),
    deleted_by varchar(100),
    CONSTRAINT credential_api_key_pkey PRIMARY KEY (id)
);

-- 4. auth.credential_bearer
CREATE TABLE IF NOT EXISTS auth.credential_bearer (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    system_code varchar(100) NOT NULL REFERENCES auth.system(code) ON DELETE CASCADE,
    traffic_type varchar(20) NOT NULL,
    header_name varchar(100) NOT NULL DEFAULT 'Authorization',
    token_prefix varchar(50) NOT NULL DEFAULT 'Bearer',
    token_value text NOT NULL,
    description text,
    status_code varchar(20) NOT NULL DEFAULT 'ACTIVE',
    created_datetime timestamp without time zone NOT NULL DEFAULT now(),
    updated_datetime timestamp without time zone,
    deleted_datetime timestamp without time zone,
    created_by varchar(100),
    updated_by varchar(100),
    deleted_by varchar(100),
    CONSTRAINT credential_bearer_pkey PRIMARY KEY (id)
);

-- 5. auth.credential_basic
CREATE TABLE IF NOT EXISTS auth.credential_basic (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    system_code varchar(100) NOT NULL REFERENCES auth.system(code) ON DELETE CASCADE,
    traffic_type varchar(20) NOT NULL,
    username varchar(255) NOT NULL,
    password text NOT NULL,
    description text,
    status_code varchar(20) NOT NULL DEFAULT 'ACTIVE',
    created_datetime timestamp without time zone NOT NULL DEFAULT now(),
    updated_datetime timestamp without time zone,
    deleted_datetime timestamp without time zone,
    created_by varchar(100),
    updated_by varchar(100),
    deleted_by varchar(100),
    CONSTRAINT credential_basic_pkey PRIMARY KEY (id)
);

COMMIT;
