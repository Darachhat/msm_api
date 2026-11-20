-- =============================================================================
-- Migration 012: Frontend Integration Columns & Stock Movement Ledger
--   - base_data.medicine: add min_stock, note
--   - data.patient: add date_out
--   - data.stock_batch: add source
--   - data.patient_dispensing: add shift_code, payment_code
--   - data.stock_movement: new table tracking IN, USAGE, EXPIRED, DAMAGED, ADJUSTMENT
-- =============================================================================

BEGIN;

-- 1. base_data.medicine
ALTER TABLE IF EXISTS base_data.medicine
    ADD COLUMN IF NOT EXISTS min_stock integer NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS note text;

-- 2. data.patient
ALTER TABLE IF EXISTS data.patient
    ADD COLUMN IF NOT EXISTS date_out date;

-- 3. data.stock_batch
ALTER TABLE IF EXISTS data.stock_batch
    ADD COLUMN IF NOT EXISTS source varchar(255);

-- 4. data.patient_dispensing
ALTER TABLE IF EXISTS data.patient_dispensing
    ADD COLUMN IF NOT EXISTS shift_code varchar(20),
    ADD COLUMN IF NOT EXISTS payment_code varchar(20);

-- 5. data.stock_movement
CREATE TABLE IF NOT EXISTS data.stock_movement (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    department_code varchar(50) NOT NULL REFERENCES base_data.department(code),
    medicine_id uuid NOT NULL REFERENCES base_data.medicine(id),
    batch_id uuid REFERENCES data.stock_batch(id) ON DELETE SET NULL,
    dispensing_item_id uuid REFERENCES data.patient_dispensing_item(id) ON DELETE SET NULL,
    movement_type varchar(20) NOT NULL,
    movement_date date NOT NULL DEFAULT CURRENT_DATE,
    quantity numeric(12, 2) NOT NULL DEFAULT 0,
    note text,
    status_code varchar(20) NOT NULL DEFAULT 'ACTIVE',
    created_datetime timestamp without time zone NOT NULL DEFAULT now(),
    updated_datetime timestamp without time zone,
    deleted_datetime timestamp without time zone,
    created_by varchar(100),
    updated_by varchar(100),
    deleted_by varchar(100),
    CONSTRAINT stock_movement_pkey PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS ix_stock_movement_med_date
    ON data.stock_movement (medicine_id, movement_date DESC)
    WHERE deleted_datetime IS NULL;

CREATE INDEX IF NOT EXISTS ix_stock_movement_batch_id
    ON data.stock_movement (batch_id)
    WHERE deleted_datetime IS NULL;

CREATE INDEX IF NOT EXISTS ix_stock_movement_dispensing_item
    ON data.stock_movement (dispensing_item_id)
    WHERE deleted_datetime IS NULL;

COMMIT;
