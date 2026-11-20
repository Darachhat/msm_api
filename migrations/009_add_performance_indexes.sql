-- =============================================================================
-- Migration 009: Performance Indexes for Hot Queries
-- =============================================================================

BEGIN;

CREATE INDEX IF NOT EXISTS ix_patient_dispensing_dept_date
    ON data.patient_dispensing (department_code, dispense_date DESC)
    WHERE deleted_datetime IS NULL;

CREATE INDEX IF NOT EXISTS ix_patient_dispensing_item_dispensing_id
    ON data.patient_dispensing_item (dispensing_id)
    WHERE deleted_datetime IS NULL;

CREATE INDEX IF NOT EXISTS ix_stock_batch_dept_med
    ON data.stock_batch (department_code, medicine_id)
    WHERE deleted_datetime IS NULL;

CREATE INDEX IF NOT EXISTS ix_report_export_dept_created
    ON data.report_export (department_code, created_datetime DESC)
    WHERE deleted_datetime IS NULL;

COMMIT;
