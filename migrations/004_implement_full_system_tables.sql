-- =============================================================================
-- Migration 004: Full System Tables (Patients, Stock Batches, Digital Signatures,
--                RBAC Service Permissions, Login History)
-- =============================================================================

BEGIN;

-- 1. auth.service_module
CREATE TABLE IF NOT EXISTS auth.service_module (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    code varchar(50) NOT NULL,
    name varchar(150) NOT NULL,
    description text,
    sort_order smallint NOT NULL DEFAULT 0,
    status_code varchar(20) NOT NULL DEFAULT 'ACTIVE',
    created_datetime timestamp without time zone NOT NULL DEFAULT now(),
    updated_datetime timestamp without time zone,
    deleted_datetime timestamp without time zone,
    created_by varchar(100),
    updated_by varchar(100),
    deleted_by varchar(100),
    CONSTRAINT service_module_pkey PRIMARY KEY (id),
    CONSTRAINT service_module_code_key UNIQUE (code)
);

-- 2. auth.role_permission
CREATE TABLE IF NOT EXISTS auth.role_permission (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    role_code varchar(50) NOT NULL REFERENCES auth.role(code) ON DELETE CASCADE,
    service_code varchar(50) NOT NULL REFERENCES auth.service_module(code) ON DELETE CASCADE,
    can_read boolean NOT NULL DEFAULT false,
    can_write boolean NOT NULL DEFAULT false,
    can_update boolean NOT NULL DEFAULT false,
    can_delete boolean NOT NULL DEFAULT false,
    status_code varchar(20) NOT NULL DEFAULT 'ACTIVE',
    created_datetime timestamp without time zone NOT NULL DEFAULT now(),
    updated_datetime timestamp without time zone,
    deleted_datetime timestamp without time zone,
    created_by varchar(100),
    updated_by varchar(100),
    deleted_by varchar(100),
    CONSTRAINT role_permission_pkey PRIMARY KEY (id),
    CONSTRAINT uq_role_permission_role_service UNIQUE (role_code, service_code)
);

-- 3. auth.login_history
CREATE TABLE IF NOT EXISTS auth.login_history (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    user_id uuid REFERENCES auth."user"(id) ON DELETE SET NULL,
    username varchar(100) NOT NULL,
    ip_address varchar(100),
    user_agent text,
    login_status varchar(20) NOT NULL,
    failure_reason varchar(255),
    login_datetime timestamp without time zone NOT NULL DEFAULT now(),
    status_code varchar(20) NOT NULL DEFAULT 'ACTIVE',
    created_datetime timestamp without time zone NOT NULL DEFAULT now(),
    updated_datetime timestamp without time zone,
    deleted_datetime timestamp without time zone,
    created_by varchar(100),
    updated_by varchar(100),
    deleted_by varchar(100),
    CONSTRAINT login_history_pkey PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS ix_login_history_datetime
    ON auth.login_history (login_datetime DESC);

-- 4. data.patient
CREATE TABLE IF NOT EXISTS data.patient (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    patient_code varchar(50),
    full_name varchar(255) NOT NULL,
    sex varchar(20),
    age varchar(20),
    diagnostic text,
    pob_province varchar(255),
    date_in date NOT NULL DEFAULT CURRENT_DATE,
    note text,
    status_code varchar(20) NOT NULL DEFAULT 'ACTIVE',
    created_datetime timestamp without time zone NOT NULL DEFAULT now(),
    updated_datetime timestamp without time zone,
    deleted_datetime timestamp without time zone,
    created_by varchar(100),
    updated_by varchar(100),
    deleted_by varchar(100),
    CONSTRAINT patient_pkey PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS ix_patient_full_name
    ON data.patient (full_name);

-- 5. data.digital_signature
CREATE TABLE IF NOT EXISTS data.digital_signature (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    user_id uuid REFERENCES auth."user"(id) ON DELETE SET NULL,
    signer_name varchar(255) NOT NULL,
    signer_role varchar(100),
    file_object_id uuid REFERENCES data.file_object(id) ON DELETE SET NULL,
    signature_data text,
    is_default boolean NOT NULL DEFAULT false,
    status_code varchar(20) NOT NULL DEFAULT 'ACTIVE',
    created_datetime timestamp without time zone NOT NULL DEFAULT now(),
    updated_datetime timestamp without time zone,
    deleted_datetime timestamp without time zone,
    created_by varchar(100),
    updated_by varchar(100),
    deleted_by varchar(100),
    CONSTRAINT digital_signature_pkey PRIMARY KEY (id)
);

-- 6. Link patient_id & signature_id to dispensing tables
ALTER TABLE data.patient_dispensing
    ADD COLUMN IF NOT EXISTS patient_id uuid REFERENCES data.patient(id) ON DELETE SET NULL;

ALTER TABLE data.patient_dispensing_item
    ADD COLUMN IF NOT EXISTS signature_id uuid REFERENCES data.digital_signature(id) ON DELETE SET NULL;

-- 7. data.stock_batch (tracks input_date & optional expire_date per stock-in)
CREATE TABLE IF NOT EXISTS data.stock_batch (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    department_code varchar(50) NOT NULL REFERENCES base_data.department(code),
    medicine_id uuid NOT NULL REFERENCES base_data.medicine(id),
    batch_no varchar(100),
    total_qty numeric(12, 2) NOT NULL DEFAULT 0,
    remaining_qty numeric(12, 2) NOT NULL DEFAULT 0,
    input_date date NOT NULL DEFAULT CURRENT_DATE,
    expire_date date,
    note text,
    status_code varchar(20) NOT NULL DEFAULT 'ACTIVE',
    created_datetime timestamp without time zone NOT NULL DEFAULT now(),
    updated_datetime timestamp without time zone,
    deleted_datetime timestamp without time zone,
    created_by varchar(100),
    updated_by varchar(100),
    deleted_by varchar(100),
    CONSTRAINT stock_batch_pkey PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS ix_stock_batch_expire_date
    ON data.stock_batch (expire_date);

-- Seed service modules
INSERT INTO auth.service_module (code, name, description, sort_order) VALUES
    ('DASHBOARD', 'Dashboard', 'Overview of stock, patients, and expiry alerts', 1),
    ('PATIENT', 'Patient', 'Patient registration and lookup', 2),
    ('STOCK', 'Stock of Medicine', 'Medicine stock batches, pills, injections, narcotics', 3),
    ('DISPENSING', 'Dispensing', 'Patient medicine dispensing records and signatures', 4),
    ('REPORT', 'Report', 'Medicine and patient reports (Daily/Weekly/Monthly) & Excel export', 5),
    ('SETTING', 'Setting', 'Users, roles, permissions, and login history', 6)
ON CONFLICT (code) DO NOTHING;

-- Seed default role permissions
INSERT INTO auth.role_permission (role_code, service_code, can_read, can_write, can_update, can_delete)
SELECT 'ADMIN', code, true, true, true, true FROM auth.service_module
ON CONFLICT (role_code, service_code) DO NOTHING;

INSERT INTO auth.role_permission (role_code, service_code, can_read, can_write, can_update, can_delete) VALUES
    ('PHARMACIST', 'DASHBOARD', true, false, false, false),
    ('PHARMACIST', 'PATIENT', true, true, true, false),
    ('PHARMACIST', 'STOCK', true, true, true, false),
    ('PHARMACIST', 'DISPENSING', true, true, true, false),
    ('PHARMACIST', 'REPORT', true, true, false, false),
    ('PHARMACIST', 'SETTING', false, false, false, false),
    ('NURSE', 'DASHBOARD', true, false, false, false),
    ('NURSE', 'PATIENT', true, true, true, false),
    ('NURSE', 'STOCK', true, false, false, false),
    ('NURSE', 'DISPENSING', true, true, true, false),
    ('NURSE', 'REPORT', true, false, false, false),
    ('NURSE', 'SETTING', false, false, false, false),
    ('VIEWER', 'DASHBOARD', true, false, false, false),
    ('VIEWER', 'PATIENT', true, false, false, false),
    ('VIEWER', 'STOCK', true, false, false, false),
    ('VIEWER', 'DISPENSING', true, false, false, false),
    ('VIEWER', 'REPORT', true, false, false, false),
    ('VIEWER', 'SETTING', false, false, false, false)
ON CONFLICT (role_code, service_code) DO NOTHING;

-- Seed report type for Patient Usage
INSERT INTO base_data.report_type (code, name, name_kh, description) VALUES
    ('PATIENT_USAGE', 'Patient Medicine Usage Report', 'របាយការណ៍ប្រើប្រាស់ឱសថតាមអ្នកជំងឺ', 'Aggregated patient medicine usage matrix (Daily/Weekly/Monthly)')
ON CONFLICT (code) DO NOTHING;

COMMIT;
