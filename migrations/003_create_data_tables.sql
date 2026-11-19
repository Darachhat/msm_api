-- =============================================================================
-- Migration 003: Create data schema tables
-- =============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS data.patient_dispensing (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    dispense_date date NOT NULL,
    department_code varchar(50) NOT NULL REFERENCES base_data.department(code),
    category_code varchar(50) NOT NULL REFERENCES base_data.medicine_category(code),
    patient_no integer,
    patient_name varchar(255) NOT NULL,
    age varchar(20),
    sex varchar(20),
    diagnostic text,
    address_province varchar(255),
    doctor_name varchar(255),
    duty_chief_name varchar(255),
    prepared_by_name varchar(255),
    note text,
    status_code varchar(20) NOT NULL DEFAULT 'ACTIVE',
    created_datetime timestamp without time zone NOT NULL DEFAULT now(),
    updated_datetime timestamp without time zone,
    deleted_datetime timestamp without time zone,
    created_by varchar(100),
    updated_by varchar(100),
    deleted_by varchar(100),
    CONSTRAINT patient_dispensing_pkey PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS ix_patient_dispensing_date
    ON data.patient_dispensing (dispense_date);

CREATE TABLE IF NOT EXISTS data.patient_dispensing_item (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    dispensing_id uuid NOT NULL REFERENCES data.patient_dispensing(id) ON DELETE CASCADE,
    medicine_id uuid NOT NULL REFERENCES base_data.medicine(id),
    quantity numeric(12, 2) NOT NULL DEFAULT 0,
    signature_note varchar(255),
    note text,
    status_code varchar(20) NOT NULL DEFAULT 'ACTIVE',
    created_datetime timestamp without time zone NOT NULL DEFAULT now(),
    updated_datetime timestamp without time zone,
    deleted_datetime timestamp without time zone,
    created_by varchar(100),
    updated_by varchar(100),
    deleted_by varchar(100),
    CONSTRAINT patient_dispensing_item_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS data.stock_ledger (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    stock_date date NOT NULL,
    department_code varchar(50) NOT NULL REFERENCES base_data.department(code),
    medicine_id uuid NOT NULL REFERENCES base_data.medicine(id),
    opening_qty numeric(12, 2) NOT NULL DEFAULT 0,
    added_qty numeric(12, 2) NOT NULL DEFAULT 0,
    used_qty numeric(12, 2) NOT NULL DEFAULT 0,
    remaining_qty numeric(12, 2) NOT NULL DEFAULT 0,
    requested_qty numeric(12, 2) NOT NULL DEFAULT 0,
    supplied_qty numeric(12, 2) NOT NULL DEFAULT 0,
    note text,
    status_code varchar(20) NOT NULL DEFAULT 'ACTIVE',
    created_datetime timestamp without time zone NOT NULL DEFAULT now(),
    updated_datetime timestamp without time zone,
    deleted_datetime timestamp without time zone,
    created_by varchar(100),
    updated_by varchar(100),
    deleted_by varchar(100),
    CONSTRAINT stock_ledger_pkey PRIMARY KEY (id),
    CONSTRAINT uq_stock_ledger_date_dept_med UNIQUE (stock_date, department_code, medicine_id)
);

CREATE INDEX IF NOT EXISTS ix_stock_ledger_date
    ON data.stock_ledger (stock_date);

CREATE TABLE IF NOT EXISTS data.file_object (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    path_code varchar(64) NOT NULL,
    title varchar(255),
    filename varchar(255) NOT NULL,
    ext varchar(20) NOT NULL,
    mime_type varchar(150) NOT NULL,
    size bigint NOT NULL DEFAULT 0,
    r2_bucket varchar(150) NOT NULL,
    r2_object_key varchar(500) NOT NULL,
    module varchar(100) NOT NULL DEFAULT 'reports',
    preview_url varchar(500),
    download_url varchar(500),
    accessed_count integer NOT NULL DEFAULT 0,
    status_code varchar(20) NOT NULL DEFAULT 'ACTIVE',
    created_datetime timestamp without time zone NOT NULL DEFAULT now(),
    updated_datetime timestamp without time zone,
    deleted_datetime timestamp without time zone,
    created_by varchar(100),
    updated_by varchar(100),
    deleted_by varchar(100),
    CONSTRAINT file_object_pkey PRIMARY KEY (id),
    CONSTRAINT file_object_path_code_key UNIQUE (path_code)
);

CREATE TABLE IF NOT EXISTS data.report_export (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    report_type_code varchar(50) NOT NULL REFERENCES base_data.report_type(code),
    department_code varchar(50) NOT NULL REFERENCES base_data.department(code),
    category_code varchar(50) REFERENCES base_data.medicine_category(code),
    medicine_id uuid REFERENCES base_data.medicine(id),
    start_date date NOT NULL,
    end_date date NOT NULL,
    file_object_id uuid NOT NULL REFERENCES data.file_object(id),
    signers_json jsonb,
    status_code varchar(20) NOT NULL DEFAULT 'ACTIVE',
    created_datetime timestamp without time zone NOT NULL DEFAULT now(),
    updated_datetime timestamp without time zone,
    deleted_datetime timestamp without time zone,
    created_by varchar(100),
    updated_by varchar(100),
    deleted_by varchar(100),
    CONSTRAINT report_export_pkey PRIMARY KEY (id)
);

COMMIT;
