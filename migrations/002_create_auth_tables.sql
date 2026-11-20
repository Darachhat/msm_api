-- =============================================================================
-- Migration 002: Create role (base_data), user (data), and refresh_token (data)
-- =============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS base_data.role (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    code varchar(50) NOT NULL,
    name varchar(150) NOT NULL,
    description text,
    translate_id uuid REFERENCES base_data.translate(id),
    status_code varchar(20) NOT NULL DEFAULT 'ACTIVE',
    created_datetime timestamp without time zone NOT NULL DEFAULT now(),
    updated_datetime timestamp without time zone,
    deleted_datetime timestamp without time zone,
    created_by varchar(100),
    updated_by varchar(100),
    deleted_by varchar(100),
    CONSTRAINT role_pkey PRIMARY KEY (id),
    CONSTRAINT role_code_key UNIQUE (code)
);

CREATE TABLE IF NOT EXISTS data."user" (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    username varchar(100) NOT NULL,
    email varchar(255),
    full_name varchar(255) NOT NULL,
    full_name_kh varchar(255),
    password_hash text NOT NULL,
    role_code varchar(50) NOT NULL DEFAULT 'PHARMACIST' REFERENCES base_data.role(code),
    department_code varchar(50) REFERENCES base_data.department(code),
    is_active boolean NOT NULL DEFAULT true,
    last_login_datetime timestamp without time zone,
    status_code varchar(20) NOT NULL DEFAULT 'ACTIVE',
    created_datetime timestamp without time zone NOT NULL DEFAULT now(),
    updated_datetime timestamp without time zone,
    deleted_datetime timestamp without time zone,
    created_by varchar(100),
    updated_by varchar(100),
    deleted_by varchar(100),
    CONSTRAINT user_pkey PRIMARY KEY (id),
    CONSTRAINT user_username_key UNIQUE (username),
    CONSTRAINT user_email_key UNIQUE (email)
);

CREATE TABLE IF NOT EXISTS data.refresh_token (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES data."user"(id) ON DELETE CASCADE,
    jti varchar(100) NOT NULL,
    expires_at timestamp without time zone NOT NULL,
    revoked boolean NOT NULL DEFAULT false,
    status_code varchar(20) NOT NULL DEFAULT 'ACTIVE',
    created_datetime timestamp without time zone NOT NULL DEFAULT now(),
    updated_datetime timestamp without time zone,
    deleted_datetime timestamp without time zone,
    created_by varchar(100),
    updated_by varchar(100),
    deleted_by varchar(100),
    CONSTRAINT refresh_token_pkey PRIMARY KEY (id),
    CONSTRAINT refresh_token_jti_key UNIQUE (jti)
);

-- Seed roles
INSERT INTO base_data.role (code, name, description) VALUES
    ('ADMIN', 'Administrator', 'Full system and user management access'),
    ('PHARMACIST', 'Pharmacist', 'Manage stock, dispensing, and generate reports'),
    ('NURSE', 'Nurse / Duty Staff', 'Record patient dispensing entries'),
    ('VIEWER', 'Viewer', 'Read-only access to reports and stock')
ON CONFLICT (code) DO NOTHING;

COMMIT;
