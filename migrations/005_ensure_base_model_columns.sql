-- =============================================================================
-- Migration 005: Ensure all tables have Base model audit columns:
--   - status_code varchar(20) NOT NULL DEFAULT 'ACTIVE'
--   - created_datetime timestamp without time zone NOT NULL DEFAULT now()
--   - updated_datetime timestamp without time zone
--   - deleted_datetime timestamp without time zone
--   - created_by varchar(100)
--   - updated_by varchar(100)
--   - deleted_by varchar(100)
-- =============================================================================

BEGIN;

-- -----------------------------------------------------------------------------
-- 1. base_data schema tables
-- -----------------------------------------------------------------------------
ALTER TABLE IF EXISTS base_data.translate
    ADD COLUMN IF NOT EXISTS status_code varchar(20) NOT NULL DEFAULT 'ACTIVE',
    ADD COLUMN IF NOT EXISTS created_datetime timestamp without time zone NOT NULL DEFAULT now(),
    ADD COLUMN IF NOT EXISTS updated_datetime timestamp without time zone,
    ADD COLUMN IF NOT EXISTS deleted_datetime timestamp without time zone,
    ADD COLUMN IF NOT EXISTS created_by varchar(100),
    ADD COLUMN IF NOT EXISTS updated_by varchar(100),
    ADD COLUMN IF NOT EXISTS deleted_by varchar(100);

ALTER TABLE IF EXISTS base_data.status
    ADD COLUMN IF NOT EXISTS status_code varchar(20) NOT NULL DEFAULT 'ACTIVE',
    ADD COLUMN IF NOT EXISTS created_datetime timestamp without time zone NOT NULL DEFAULT now(),
    ADD COLUMN IF NOT EXISTS updated_datetime timestamp without time zone,
    ADD COLUMN IF NOT EXISTS deleted_datetime timestamp without time zone,
    ADD COLUMN IF NOT EXISTS created_by varchar(100),
    ADD COLUMN IF NOT EXISTS updated_by varchar(100),
    ADD COLUMN IF NOT EXISTS deleted_by varchar(100);

ALTER TABLE IF EXISTS base_data.role
    ADD COLUMN IF NOT EXISTS status_code varchar(20) NOT NULL DEFAULT 'ACTIVE',
    ADD COLUMN IF NOT EXISTS created_datetime timestamp without time zone NOT NULL DEFAULT now(),
    ADD COLUMN IF NOT EXISTS updated_datetime timestamp without time zone,
    ADD COLUMN IF NOT EXISTS deleted_datetime timestamp without time zone,
    ADD COLUMN IF NOT EXISTS created_by varchar(100),
    ADD COLUMN IF NOT EXISTS updated_by varchar(100),
    ADD COLUMN IF NOT EXISTS deleted_by varchar(100);

ALTER TABLE IF EXISTS base_data.service_module
    ADD COLUMN IF NOT EXISTS status_code varchar(20) NOT NULL DEFAULT 'ACTIVE',
    ADD COLUMN IF NOT EXISTS created_datetime timestamp without time zone NOT NULL DEFAULT now(),
    ADD COLUMN IF NOT EXISTS updated_datetime timestamp without time zone,
    ADD COLUMN IF NOT EXISTS deleted_datetime timestamp without time zone,
    ADD COLUMN IF NOT EXISTS created_by varchar(100),
    ADD COLUMN IF NOT EXISTS updated_by varchar(100),
    ADD COLUMN IF NOT EXISTS deleted_by varchar(100);

ALTER TABLE IF EXISTS base_data.role_permission
    ADD COLUMN IF NOT EXISTS status_code varchar(20) NOT NULL DEFAULT 'ACTIVE',
    ADD COLUMN IF NOT EXISTS created_datetime timestamp without time zone NOT NULL DEFAULT now(),
    ADD COLUMN IF NOT EXISTS updated_datetime timestamp without time zone,
    ADD COLUMN IF NOT EXISTS deleted_datetime timestamp without time zone,
    ADD COLUMN IF NOT EXISTS created_by varchar(100),
    ADD COLUMN IF NOT EXISTS updated_by varchar(100),
    ADD COLUMN IF NOT EXISTS deleted_by varchar(100);

ALTER TABLE IF EXISTS base_data.department
    ADD COLUMN IF NOT EXISTS status_code varchar(20) NOT NULL DEFAULT 'ACTIVE',
    ADD COLUMN IF NOT EXISTS created_datetime timestamp without time zone NOT NULL DEFAULT now(),
    ADD COLUMN IF NOT EXISTS updated_datetime timestamp without time zone,
    ADD COLUMN IF NOT EXISTS deleted_datetime timestamp without time zone,
    ADD COLUMN IF NOT EXISTS created_by varchar(100),
    ADD COLUMN IF NOT EXISTS updated_by varchar(100),
    ADD COLUMN IF NOT EXISTS deleted_by varchar(100);

ALTER TABLE IF EXISTS base_data.medicine_category
    ADD COLUMN IF NOT EXISTS status_code varchar(20) NOT NULL DEFAULT 'ACTIVE',
    ADD COLUMN IF NOT EXISTS created_datetime timestamp without time zone NOT NULL DEFAULT now(),
    ADD COLUMN IF NOT EXISTS updated_datetime timestamp without time zone,
    ADD COLUMN IF NOT EXISTS deleted_datetime timestamp without time zone,
    ADD COLUMN IF NOT EXISTS created_by varchar(100),
    ADD COLUMN IF NOT EXISTS updated_by varchar(100),
    ADD COLUMN IF NOT EXISTS deleted_by varchar(100);

ALTER TABLE IF EXISTS base_data.medicine_form
    ADD COLUMN IF NOT EXISTS status_code varchar(20) NOT NULL DEFAULT 'ACTIVE',
    ADD COLUMN IF NOT EXISTS created_datetime timestamp without time zone NOT NULL DEFAULT now(),
    ADD COLUMN IF NOT EXISTS updated_datetime timestamp without time zone,
    ADD COLUMN IF NOT EXISTS deleted_datetime timestamp without time zone,
    ADD COLUMN IF NOT EXISTS created_by varchar(100),
    ADD COLUMN IF NOT EXISTS updated_by varchar(100),
    ADD COLUMN IF NOT EXISTS deleted_by varchar(100);

ALTER TABLE IF EXISTS base_data.medicine
    ADD COLUMN IF NOT EXISTS status_code varchar(20) NOT NULL DEFAULT 'ACTIVE',
    ADD COLUMN IF NOT EXISTS created_datetime timestamp without time zone NOT NULL DEFAULT now(),
    ADD COLUMN IF NOT EXISTS updated_datetime timestamp without time zone,
    ADD COLUMN IF NOT EXISTS deleted_datetime timestamp without time zone,
    ADD COLUMN IF NOT EXISTS created_by varchar(100),
    ADD COLUMN IF NOT EXISTS updated_by varchar(100),
    ADD COLUMN IF NOT EXISTS deleted_by varchar(100);

ALTER TABLE IF EXISTS base_data.report_type
    ADD COLUMN IF NOT EXISTS status_code varchar(20) NOT NULL DEFAULT 'ACTIVE',
    ADD COLUMN IF NOT EXISTS created_datetime timestamp without time zone NOT NULL DEFAULT now(),
    ADD COLUMN IF NOT EXISTS updated_datetime timestamp without time zone,
    ADD COLUMN IF NOT EXISTS deleted_datetime timestamp without time zone,
    ADD COLUMN IF NOT EXISTS created_by varchar(100),
    ADD COLUMN IF NOT EXISTS updated_by varchar(100),
    ADD COLUMN IF NOT EXISTS deleted_by varchar(100);

-- -----------------------------------------------------------------------------
-- 2. data schema tables
-- -----------------------------------------------------------------------------
ALTER TABLE IF EXISTS data."user"
    ADD COLUMN IF NOT EXISTS status_code varchar(20) NOT NULL DEFAULT 'ACTIVE',
    ADD COLUMN IF NOT EXISTS created_datetime timestamp without time zone NOT NULL DEFAULT now(),
    ADD COLUMN IF NOT EXISTS updated_datetime timestamp without time zone,
    ADD COLUMN IF NOT EXISTS deleted_datetime timestamp without time zone,
    ADD COLUMN IF NOT EXISTS created_by varchar(100),
    ADD COLUMN IF NOT EXISTS updated_by varchar(100),
    ADD COLUMN IF NOT EXISTS deleted_by varchar(100);

ALTER TABLE IF EXISTS data.refresh_token
    ADD COLUMN IF NOT EXISTS status_code varchar(20) NOT NULL DEFAULT 'ACTIVE',
    ADD COLUMN IF NOT EXISTS created_datetime timestamp without time zone NOT NULL DEFAULT now(),
    ADD COLUMN IF NOT EXISTS updated_datetime timestamp without time zone,
    ADD COLUMN IF NOT EXISTS deleted_datetime timestamp without time zone,
    ADD COLUMN IF NOT EXISTS created_by varchar(100),
    ADD COLUMN IF NOT EXISTS updated_by varchar(100),
    ADD COLUMN IF NOT EXISTS deleted_by varchar(100);

ALTER TABLE IF EXISTS data.patient
    ADD COLUMN IF NOT EXISTS status_code varchar(20) NOT NULL DEFAULT 'ACTIVE',
    ADD COLUMN IF NOT EXISTS created_datetime timestamp without time zone NOT NULL DEFAULT now(),
    ADD COLUMN IF NOT EXISTS updated_datetime timestamp without time zone,
    ADD COLUMN IF NOT EXISTS deleted_datetime timestamp without time zone,
    ADD COLUMN IF NOT EXISTS created_by varchar(100),
    ADD COLUMN IF NOT EXISTS updated_by varchar(100),
    ADD COLUMN IF NOT EXISTS deleted_by varchar(100);

ALTER TABLE IF EXISTS data.patient_dispensing
    ADD COLUMN IF NOT EXISTS status_code varchar(20) NOT NULL DEFAULT 'ACTIVE',
    ADD COLUMN IF NOT EXISTS created_datetime timestamp without time zone NOT NULL DEFAULT now(),
    ADD COLUMN IF NOT EXISTS updated_datetime timestamp without time zone,
    ADD COLUMN IF NOT EXISTS deleted_datetime timestamp without time zone,
    ADD COLUMN IF NOT EXISTS created_by varchar(100),
    ADD COLUMN IF NOT EXISTS updated_by varchar(100),
    ADD COLUMN IF NOT EXISTS deleted_by varchar(100);

ALTER TABLE IF EXISTS data.patient_dispensing_item
    ADD COLUMN IF NOT EXISTS status_code varchar(20) NOT NULL DEFAULT 'ACTIVE',
    ADD COLUMN IF NOT EXISTS created_datetime timestamp without time zone NOT NULL DEFAULT now(),
    ADD COLUMN IF NOT EXISTS updated_datetime timestamp without time zone,
    ADD COLUMN IF NOT EXISTS deleted_datetime timestamp without time zone,
    ADD COLUMN IF NOT EXISTS created_by varchar(100),
    ADD COLUMN IF NOT EXISTS updated_by varchar(100),
    ADD COLUMN IF NOT EXISTS deleted_by varchar(100);

ALTER TABLE IF EXISTS data.stock_ledger
    ADD COLUMN IF NOT EXISTS status_code varchar(20) NOT NULL DEFAULT 'ACTIVE',
    ADD COLUMN IF NOT EXISTS created_datetime timestamp without time zone NOT NULL DEFAULT now(),
    ADD COLUMN IF NOT EXISTS updated_datetime timestamp without time zone,
    ADD COLUMN IF NOT EXISTS deleted_datetime timestamp without time zone,
    ADD COLUMN IF NOT EXISTS created_by varchar(100),
    ADD COLUMN IF NOT EXISTS updated_by varchar(100),
    ADD COLUMN IF NOT EXISTS deleted_by varchar(100);

ALTER TABLE IF EXISTS data.stock_batch
    ADD COLUMN IF NOT EXISTS status_code varchar(20) NOT NULL DEFAULT 'ACTIVE',
    ADD COLUMN IF NOT EXISTS created_datetime timestamp without time zone NOT NULL DEFAULT now(),
    ADD COLUMN IF NOT EXISTS updated_datetime timestamp without time zone,
    ADD COLUMN IF NOT EXISTS deleted_datetime timestamp without time zone,
    ADD COLUMN IF NOT EXISTS created_by varchar(100),
    ADD COLUMN IF NOT EXISTS updated_by varchar(100),
    ADD COLUMN IF NOT EXISTS deleted_by varchar(100);

ALTER TABLE IF EXISTS data.file_object
    ADD COLUMN IF NOT EXISTS status_code varchar(20) NOT NULL DEFAULT 'ACTIVE',
    ADD COLUMN IF NOT EXISTS created_datetime timestamp without time zone NOT NULL DEFAULT now(),
    ADD COLUMN IF NOT EXISTS updated_datetime timestamp without time zone,
    ADD COLUMN IF NOT EXISTS deleted_datetime timestamp without time zone,
    ADD COLUMN IF NOT EXISTS created_by varchar(100),
    ADD COLUMN IF NOT EXISTS updated_by varchar(100),
    ADD COLUMN IF NOT EXISTS deleted_by varchar(100);

ALTER TABLE IF EXISTS data.digital_signature
    ADD COLUMN IF NOT EXISTS status_code varchar(20) NOT NULL DEFAULT 'ACTIVE',
    ADD COLUMN IF NOT EXISTS created_datetime timestamp without time zone NOT NULL DEFAULT now(),
    ADD COLUMN IF NOT EXISTS updated_datetime timestamp without time zone,
    ADD COLUMN IF NOT EXISTS deleted_datetime timestamp without time zone,
    ADD COLUMN IF NOT EXISTS created_by varchar(100),
    ADD COLUMN IF NOT EXISTS updated_by varchar(100),
    ADD COLUMN IF NOT EXISTS deleted_by varchar(100);

ALTER TABLE IF EXISTS data.report_export
    ADD COLUMN IF NOT EXISTS status_code varchar(20) NOT NULL DEFAULT 'ACTIVE',
    ADD COLUMN IF NOT EXISTS created_datetime timestamp without time zone NOT NULL DEFAULT now(),
    ADD COLUMN IF NOT EXISTS updated_datetime timestamp without time zone,
    ADD COLUMN IF NOT EXISTS deleted_datetime timestamp without time zone,
    ADD COLUMN IF NOT EXISTS created_by varchar(100),
    ADD COLUMN IF NOT EXISTS updated_by varchar(100),
    ADD COLUMN IF NOT EXISTS deleted_by varchar(100);

COMMIT;
