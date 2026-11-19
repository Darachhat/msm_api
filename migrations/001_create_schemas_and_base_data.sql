-- =============================================================================
-- Migration 001: Create schemas (auth, base_data, data) & base_data tables + seeds
-- =============================================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS auth;
CREATE SCHEMA IF NOT EXISTS base_data;
CREATE SCHEMA IF NOT EXISTS data;

-- 1. base_data.translate
CREATE TABLE IF NOT EXISTS base_data.translate (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    ref_id uuid NOT NULL,
    schema_name varchar(100) NOT NULL,
    table_name varchar(100) NOT NULL,
    column_name varchar(100) NOT NULL,
    en text,
    km text,
    cn text,
    jp text,
    kr text,
    note text,
    status_code varchar(20) NOT NULL DEFAULT 'ACTIVE',
    created_datetime timestamp without time zone NOT NULL DEFAULT now(),
    updated_datetime timestamp without time zone,
    deleted_datetime timestamp without time zone,
    created_by varchar(100),
    updated_by varchar(100),
    deleted_by varchar(100),
    CONSTRAINT translate_pkey PRIMARY KEY (id)
);

-- 2. base_data.status
CREATE TABLE IF NOT EXISTS base_data.status (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    code varchar(100) NOT NULL,
    name varchar(255) NOT NULL,
    translate_id uuid REFERENCES base_data.translate(id),
    status_code varchar(20) NOT NULL DEFAULT 'ACTIVE',
    created_datetime timestamp without time zone NOT NULL DEFAULT now(),
    updated_datetime timestamp without time zone,
    deleted_datetime timestamp without time zone,
    created_by varchar(100),
    updated_by varchar(100),
    deleted_by varchar(100),
    CONSTRAINT status_pkey PRIMARY KEY (id),
    CONSTRAINT status_code_key UNIQUE (code)
);

-- 3. base_data.department
CREATE TABLE IF NOT EXISTS base_data.department (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    code varchar(50) NOT NULL,
    name varchar(255) NOT NULL,
    name_kh varchar(255) NOT NULL,
    hospital_name varchar(255),
    hospital_name_kh varchar(255),
    doc_number varchar(50),
    translate_id uuid REFERENCES base_data.translate(id),
    status_code varchar(20) NOT NULL DEFAULT 'ACTIVE',
    created_datetime timestamp without time zone NOT NULL DEFAULT now(),
    updated_datetime timestamp without time zone,
    deleted_datetime timestamp without time zone,
    created_by varchar(100),
    updated_by varchar(100),
    deleted_by varchar(100),
    CONSTRAINT department_pkey PRIMARY KEY (id),
    CONSTRAINT department_code_key UNIQUE (code)
);

-- 4. base_data.medicine_category
CREATE TABLE IF NOT EXISTS base_data.medicine_category (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    code varchar(50) NOT NULL,
    name varchar(150) NOT NULL,
    name_kh varchar(150) NOT NULL,
    record_order smallint NOT NULL DEFAULT 0,
    translate_id uuid REFERENCES base_data.translate(id),
    status_code varchar(20) NOT NULL DEFAULT 'ACTIVE',
    created_datetime timestamp without time zone NOT NULL DEFAULT now(),
    updated_datetime timestamp without time zone,
    deleted_datetime timestamp without time zone,
    created_by varchar(100),
    updated_by varchar(100),
    deleted_by varchar(100),
    CONSTRAINT medicine_category_pkey PRIMARY KEY (id),
    CONSTRAINT medicine_category_code_key UNIQUE (code)
);

-- 5. base_data.medicine_form
CREATE TABLE IF NOT EXISTS base_data.medicine_form (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    code varchar(50) NOT NULL,
    name varchar(100) NOT NULL,
    name_kh varchar(100),
    unit_label varchar(50),
    record_order smallint NOT NULL DEFAULT 0,
    status_code varchar(20) NOT NULL DEFAULT 'ACTIVE',
    created_datetime timestamp without time zone NOT NULL DEFAULT now(),
    updated_datetime timestamp without time zone,
    deleted_datetime timestamp without time zone,
    created_by varchar(100),
    updated_by varchar(100),
    deleted_by varchar(100),
    CONSTRAINT medicine_form_pkey PRIMARY KEY (id),
    CONSTRAINT medicine_form_code_key UNIQUE (code)
);

-- 6. base_data.medicine
CREATE TABLE IF NOT EXISTS base_data.medicine (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    code varchar(100) NOT NULL,
    name varchar(255) NOT NULL,
    category_code varchar(50) NOT NULL REFERENCES base_data.medicine_category(code),
    form_code varchar(50) NOT NULL REFERENCES base_data.medicine_form(code),
    dosage varchar(100),
    unit_label varchar(50),
    is_narcotic boolean NOT NULL DEFAULT false,
    narcotic_doc_no varchar(50),
    sort_order integer NOT NULL DEFAULT 0,
    translate_id uuid REFERENCES base_data.translate(id),
    status_code varchar(20) NOT NULL DEFAULT 'ACTIVE',
    created_datetime timestamp without time zone NOT NULL DEFAULT now(),
    updated_datetime timestamp without time zone,
    deleted_datetime timestamp without time zone,
    created_by varchar(100),
    updated_by varchar(100),
    deleted_by varchar(100),
    CONSTRAINT medicine_pkey PRIMARY KEY (id),
    CONSTRAINT medicine_code_key UNIQUE (code)
);

-- 7. base_data.report_type
CREATE TABLE IF NOT EXISTS base_data.report_type (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    code varchar(50) NOT NULL,
    name varchar(255) NOT NULL,
    name_kh varchar(255),
    description text,
    status_code varchar(20) NOT NULL DEFAULT 'ACTIVE',
    created_datetime timestamp without time zone NOT NULL DEFAULT now(),
    updated_datetime timestamp without time zone,
    deleted_datetime timestamp without time zone,
    created_by varchar(100),
    updated_by varchar(100),
    deleted_by varchar(100),
    CONSTRAINT report_type_pkey PRIMARY KEY (id),
    CONSTRAINT report_type_code_key UNIQUE (code)
);

-- Seed statuses
INSERT INTO base_data.status (code, name) VALUES
    ('ACTIVE', 'Active'),
    ('INACTIVE', 'Inactive'),
    ('DRAFT', 'Draft'),
    ('ARCHIVED', 'Archived'),
    ('DELETED', 'Deleted')
ON CONFLICT (code) DO NOTHING;

-- Seed department
INSERT INTO base_data.department (code, name, name_kh, hospital_name, hospital_name_kh, doc_number) VALUES
    ('SURGICAL_ICU', 'Surgical Intensive Care Unit', 'ផ្នែកប្រពោធនកម្មសល្យសាស្រ្ត', 'Khmer-Soviet Friendship Hospital', 'មន្ទីរពេទ្យមិត្តភាពខ្មែរ-សូវៀត', '101')
ON CONFLICT (code) DO NOTHING;

-- Seed categories
INSERT INTO base_data.medicine_category (code, name, name_kh, record_order) VALUES
    ('TABLET', 'Tablet / Oral', 'ថ្នាំគ្រាប់', 1),
    ('INJECTION', 'Injection / Parenteral', 'ថ្នាំចាក់', 2)
ON CONFLICT (code) DO NOTHING;

-- Seed forms
INSERT INTO base_data.medicine_form (code, name, name_kh, unit_label, record_order) VALUES
    ('TABLET', 'គ្រាប់', 'គ្រាប់', 'គ្រាប់', 1),
    ('AMP', 'Amp', 'អំពូល', 'អំពូល', 2),
    ('FL', 'FL', 'ដប (FL)', 'FL', 3),
    ('SOLUTION', 'Solution', 'សូលុយស្យុង', 'Solution', 4),
    ('GEL', 'Gel', 'ជែល', 'Gel', 5),
    ('AEROSOL', 'Aerosol', 'បាញ់', 'Aerosol', 6)
ON CONFLICT (code) DO NOTHING;

-- Seed report types
INSERT INTO base_data.report_type (code, name, name_kh, description) VALUES
    ('DAILY_USAGE', 'Daily Patient Medicine Usage', 'របាយការណ៍ឪសថ បរិក្ខាពេទ្យ សំរាប់ឪសថយាម/ផ្នែកបច្ចេកទេស', 'Wide matrix of daily patient dispensing per medicine'),
    ('DAILY_STOCK', 'Daily Stock Income-Expense', 'របាយការណ៍ ចំណូល-ចំណាយ សម្ភារៈបរិក្ខាពេទ្យ-ឪសថប្រចាំថ្ងៃ', 'Daily opening, added, total, and remaining stock'),
    ('WEEKLY_USAGE_REQUEST', 'Weekly Medicine Usage & Request', 'របាយការណ៍ចំណូលចំណាយ និងសំណើឱសថ', 'Multi-day usage breakdown with stock balance and request/supply'),
    ('NARCOTIC_USAGE', 'Narcotic Analgesic Usage', 'របាយការណ៍ប្រើប្រាស់ឱសថមានសារធាតុញៀន', 'Per-narcotic drug patient dispensing register with 3-role approval')
ON CONFLICT (code) DO NOTHING;

-- Seed all 146 medicines (44 tablets + 102 injections/other)
INSERT INTO base_data.medicine (code, name, category_code, form_code, dosage, unit_label, is_narcotic, narcotic_doc_no, sort_order) VALUES
    ('TAB_AMLODIPINE', 'Amlodipine', 'TABLET', 'TABLET', NULL, 'គ្រាប់', FALSE, NULL, 1),
    ('TAB_AMOXILLINE', 'Amoxilline', 'TABLET', 'TABLET', NULL, 'គ្រាប់', FALSE, NULL, 2),
    ('TAB_AUGMENTIN', 'Augmentin', 'TABLET', 'TABLET', NULL, 'គ្រាប់', FALSE, NULL, 3),
    ('TAB_ASPIRINE', 'Aspirine', 'TABLET', 'TABLET', NULL, 'គ្រាប់', FALSE, NULL, 4),
    ('TAB_AZITHROMYCINE', 'Azithromycine', 'TABLET', 'TABLET', NULL, 'គ្រាប់', FALSE, NULL, 5),
    ('TAB_BICARBONATE', 'Bicarbonate', 'TABLET', 'TABLET', NULL, 'គ្រាប់', FALSE, NULL, 6),
    ('TAB_BROMHEXINE', 'Bromhexine', 'TABLET', 'TABLET', NULL, 'គ្រាប់', FALSE, NULL, 7),
    ('TAB_CATAPRESSAN', 'Catapressan', 'TABLET', 'TABLET', NULL, 'គ្រាប់', FALSE, NULL, 8),
    ('TAB_CEFTIRINE_10MG', 'Ceftirine 10mg', 'TABLET', 'TABLET', NULL, 'គ្រាប់', FALSE, NULL, 9),
    ('TAB_CINACALCET', 'Cinacalcet', 'TABLET', 'TABLET', NULL, 'គ្រាប់', FALSE, NULL, 10),
    ('TAB_CLODERM_CREAM', 'Cloderm Cream', 'TABLET', 'TABLET', NULL, 'គ្រាប់', FALSE, NULL, 11),
    ('TAB_COTRIM', 'Cotrim', 'TABLET', 'TABLET', NULL, 'គ្រាប់', FALSE, NULL, 12),
    ('TAB_COVERAM', 'Coveram', 'TABLET', 'TABLET', NULL, 'គ្រាប់', FALSE, NULL, 13),
    ('TAB_DETRAN', 'Detran', 'TABLET', 'TABLET', NULL, 'គ្រាប់', FALSE, NULL, 14),
    ('TAB_DIAZEPAM', 'Diazepam', 'TABLET', 'TABLET', NULL, 'គ្រាប់', FALSE, NULL, 15),
    ('TAB_DUPHALAC', 'Duphalac', 'TABLET', 'TABLET', NULL, 'គ្រាប់', FALSE, NULL, 16),
    ('TAB_EMPIGET', 'Empiget', 'TABLET', 'TABLET', NULL, 'គ្រាប់', FALSE, NULL, 17),
    ('TAB_K_CHECK', 'K-check', 'TABLET', 'TABLET', NULL, 'គ្រាប់', FALSE, NULL, 18),
    ('TAB_LACTULOSE', 'Lactulose', 'TABLET', 'TABLET', NULL, 'គ្រាប់', FALSE, NULL, 19),
    ('TAB_LEPIVAT', 'Lepivat', 'TABLET', 'TABLET', NULL, 'គ្រាប់', FALSE, NULL, 20),
    ('TAB_LOSARTAN', 'Losartan', 'TABLET', 'TABLET', NULL, 'គ្រាប់', FALSE, NULL, 21),
    ('TAB_MESTINON', 'Mestinon', 'TABLET', 'TABLET', NULL, 'គ្រាប់', FALSE, NULL, 22),
    ('TAB_MOXIFLOXAXINE', 'Moxifloxaxine', 'TABLET', 'TABLET', NULL, 'គ្រាប់', FALSE, NULL, 23),
    ('TAB_MULTIVITAMINE', 'Multivitamine', 'TABLET', 'TABLET', NULL, 'គ្រាប់', FALSE, NULL, 24),
    ('TAB_NIMOTOP', 'Nimotop', 'TABLET', 'TABLET', NULL, 'គ្រាប់', FALSE, NULL, 25),
    ('TAB_NIFURATOINE', 'Nifuratoine', 'TABLET', 'TABLET', NULL, 'គ្រាប់', FALSE, NULL, 26),
    ('TAB_NORMACOL', 'Normacol', 'TABLET', 'TABLET', NULL, 'គ្រាប់', FALSE, NULL, 27),
    ('TAB_PARACETAMOL', 'Paracetamol', 'TABLET', 'TABLET', NULL, 'គ្រាប់', FALSE, NULL, 28),
    ('TAB_PHENOBARBITAL', 'Phenobarbital', 'TABLET', 'TABLET', NULL, 'គ្រាប់', FALSE, NULL, 29),
    ('TAB_PROPRANOLOL', 'Propranolol', 'TABLET', 'TABLET', NULL, 'គ្រាប់', FALSE, NULL, 30),
    ('TAB_PROPYLTHIOURCIL', 'Propylthiourcil', 'TABLET', 'TABLET', NULL, 'គ្រាប់', FALSE, NULL, 31),
    ('TAB_ROLEX', 'Rolex', 'TABLET', 'TABLET', NULL, 'គ្រាប់', FALSE, NULL, 32),
    ('TAB_SAFCOR', 'Safcor', 'TABLET', 'TABLET', NULL, 'គ្រាប់', FALSE, NULL, 33),
    ('TAB_SEPTYL_MOUTH_WASH', 'Septyl Mouth wash', 'TABLET', 'TABLET', NULL, 'គ្រាប់', FALSE, NULL, 34),
    ('TAB_SEVELAMER', 'Sevelamer', 'TABLET', 'TABLET', NULL, 'គ្រាប់', FALSE, NULL, 35),
    ('TAB_SODIUM_CHLORIDE', 'Sodium Chloride', 'TABLET', 'TABLET', NULL, 'គ្រាប់', FALSE, NULL, 36),
    ('TAB_SOTIO', 'Sotio', 'TABLET', 'TABLET', NULL, 'គ្រាប់', FALSE, NULL, 37),
    ('TAB_TASMI', 'Tasmi', 'TABLET', 'TABLET', NULL, 'គ្រាប់', FALSE, NULL, 38),
    ('TAB_TAMIFLU', 'Tamiflu', 'TABLET', 'TABLET', NULL, 'គ្រាប់', FALSE, NULL, 39),
    ('TAB_TAMSOLIN', 'Tamsolin', 'TABLET', 'TABLET', NULL, 'គ្រាប់', FALSE, NULL, 40),
    ('TAB_TELMISARTAN', 'Telmisartan', 'TABLET', 'TABLET', NULL, 'គ្រាប់', FALSE, NULL, 41),
    ('TAB_TOBRAMYCINE', 'Tobramycine', 'TABLET', 'TABLET', NULL, 'គ្រាប់', FALSE, NULL, 42),
    ('TAB_UCHLORINE', 'Uchlorine', 'TABLET', 'TABLET', NULL, 'គ្រាប់', FALSE, NULL, 43),
    ('TAB_VITAMINE_B1B6B12', 'Vitamine B1B6B12', 'TABLET', 'TABLET', NULL, 'គ្រាប់', FALSE, NULL, 44),
    ('INJ_ADR_NALINE_1MG', 'Adrénaline', 'INJECTION', 'AMP', '1mg', 'Amp', FALSE, NULL, 1),
    ('INJ_ADENOSIM_6MG', 'Adenosim', 'INJECTION', 'AMP', '6mg', 'Amp', FALSE, NULL, 2),
    ('INJ_ALBUMINE_10G', 'Albumine', 'INJECTION', 'FL', '10g', 'FL', FALSE, NULL, 3),
    ('INJ_ATROPINE_1MG', 'Atropine', 'INJECTION', 'AMP', '1mg', 'Amp', FALSE, NULL, 4),
    ('INJ_AMIKACINE_500MG', 'Amikacine', 'INJECTION', 'FL', '500mg', 'FL', FALSE, NULL, 5),
    ('INJ_AMIODARONE_150MG', 'Amiodarone', 'INJECTION', 'AMP', '150mg', 'Amp', FALSE, NULL, 6),
    ('INJ_AMINOPLASMA_500ML', 'Aminoplasma', 'INJECTION', 'FL', '500ml', 'FL', FALSE, NULL, 7),
    ('INJ_AMPICILLINE_1G', 'Ampicilline', 'INJECTION', 'FL', '1g', 'FL', FALSE, NULL, 8),
    ('INJ_AUGMENTIN_1G', 'Augmentin', 'INJECTION', 'FL', '1g', 'FL', FALSE, NULL, 9),
    ('INJ_BICARBONATE_DE_SODIUM_1G', 'Bicarbonate de sodium', 'INJECTION', 'AMP', '1g', 'Amp', FALSE, NULL, 10),
    ('INJ_BROMHEXINE_8MG', 'Bromhexine', 'INJECTION', 'AMP', '8mg', 'Amp', FALSE, NULL, 11),
    ('INJ_BRAINACT_1G', 'Brainact', 'INJECTION', 'AMP', '1g', 'Amp', FALSE, NULL, 12),
    ('INJ_BUTHYLHYOSCINE_20MG', 'Buthylhyoscine', 'INJECTION', 'AMP', '20mg', 'Amp', FALSE, NULL, 13),
    ('INJ_BUTORPHANOL_2MG', 'Butorphanol', 'INJECTION', 'AMP', '2mg', 'អំពូល', TRUE, '95', 14),
    ('INJ_BUTORPHANOL_1MG', 'Butorphanol', 'INJECTION', 'AMP', '1mg', 'អំពូល', TRUE, '95', 15),
    ('INJ_CALCIUM_GLUCONATE_500MG', 'Calcium Gluconate', 'INJECTION', 'AMP', '500mg', 'Amp', FALSE, NULL, 16),
    ('INJ_CEFTRIAXONE_1G', 'Ceftriaxone', 'INJECTION', 'FL', '1g', 'FL', FALSE, NULL, 17),
    ('INJ_CEFTAZIDIME_1G', 'Ceftazidime', 'INJECTION', 'FL', '1g', 'FL', FALSE, NULL, 18),
    ('INJ_CEFRACTAM_1G', 'Cefractam', 'INJECTION', 'FL', '1g', 'FL', FALSE, NULL, 19),
    ('INJ_CIMETIDINE_200MG', 'Cimetidine', 'INJECTION', 'AMP', '200mg', 'Amp', FALSE, NULL, 20),
    ('INJ_CIPROFLOXACINE_200MG', 'Ciprofloxacine', 'INJECTION', 'FL', '200mg', 'FL', FALSE, NULL, 21),
    ('INJ_CHLORPROMAZINE_50MG', 'Chlorpromazine', 'INJECTION', 'AMP', '50mg', 'Amp', FALSE, NULL, 22),
    ('INJ_CLINDAMYCINE_300MG', 'Clindamycine', 'INJECTION', 'AMP', '300mg', 'Amp', FALSE, NULL, 23),
    ('INJ_DEXAMETHASONE_4MG', 'Dexamethasone', 'INJECTION', 'AMP', '4mg', 'Amp', FALSE, NULL, 24),
    ('INJ_DIAZEPAM_10MG', 'Diazepam', 'INJECTION', 'AMP', '10mg', 'Amp', FALSE, NULL, 25),
    ('INJ_DICYNONE_250MG', 'Dicynone', 'INJECTION', 'AMP', '250mg', 'Amp', FALSE, NULL, 26),
    ('INJ_DICLOFENAC_1ML', 'Diclofenac', 'INJECTION', 'AMP', '1ml', 'Amp', FALSE, NULL, 27),
    ('INJ_DIGOXIN_5MG', 'Digoxin', 'INJECTION', 'AMP', '5mg', 'Amp', FALSE, NULL, 28),
    ('INJ_DOBUTAMINE_250MG', 'Dobutamine', 'INJECTION', 'FL', '250mg', 'FL', FALSE, NULL, 29),
    ('INJ_DOPAMINE_200MG', 'Dopamine', 'INJECTION', 'AMP', '200mg', 'Amp', FALSE, NULL, 30),
    ('INJ_ERYTROMYCINE_500MG', 'Erytromycine', 'INJECTION', 'FL', '500mg', 'FL', FALSE, NULL, 31),
    ('INJ_FENTANYL_100_G', 'Fentanyl', 'INJECTION', 'AMP', '100µg', 'អំពូល', TRUE, '101', 32),
    ('INJ_FUROSEMIDE_20MG', 'Furosemide', 'INJECTION', 'AMP', '20mg', 'Amp', FALSE, NULL, 33),
    ('INJ_GENTAMYCINE_80MG', 'Gentamycine', 'INJECTION', 'AMP', '80mg', 'Amp', FALSE, NULL, 34),
    ('INJ_GLYCERINE', 'Glycerine', 'INJECTION', 'FL', NULL, 'FL', FALSE, NULL, 35),
    ('INJ_GLUCOSE_50ML', 'Glucose', 'INJECTION', 'FL', '50ml', 'FL', FALSE, NULL, 36),
    ('INJ_GLUCOSE_10ML', 'Glucose', 'INJECTION', 'AMP', '10ml', 'Amp', FALSE, NULL, 37),
    ('INJ_HALOPERIDOL_10MG', 'Haloperidol', 'INJECTION', 'AMP', '10mg', 'Amp', FALSE, NULL, 38),
    ('INJ_HEPAGART_10ML', 'Hepagart', 'INJECTION', 'AMP', '10ml', 'Amp', FALSE, NULL, 39),
    ('INJ_HEPARINE_5ML', 'Heparine', 'INJECTION', 'FL', '5ml', 'FL', FALSE, NULL, 40),
    ('INJ_HYDRALAZINE_20MG', 'Hydralazine', 'INJECTION', 'AMP', '20mg', 'Amp', FALSE, NULL, 41),
    ('INJ_HYDROCORTISONE_100MG', 'Hydrocortisone', 'INJECTION', 'FL', '100mg', 'FL', FALSE, NULL, 42),
    ('INJ_INSULINE_ACTRAPIDE_20MG', 'Insuline Actrapide', 'INJECTION', 'FL', '20mg', 'FL', FALSE, NULL, 43),
    ('INJ_KABIVEN', 'Kabiven', 'INJECTION', 'FL', NULL, 'FL', FALSE, NULL, 44),
    ('INJ_KETAMINE_500MG', 'Ketamine', 'INJECTION', 'FL', '500mg', 'FL', TRUE, '101', 45),
    ('INJ_LEVEGET_500MG', 'Leveget', 'INJECTION', 'FL', '500mg', 'FL', FALSE, NULL, 46),
    ('INJ_LEVOFLXACINE_500ML', 'Levoflxacine', 'INJECTION', 'FL', '500ml', 'FL', FALSE, NULL, 47),
    ('INJ_LIDOCAINE_2', 'Lidocaine', 'INJECTION', 'FL', '2%', 'FL', FALSE, NULL, 48),
    ('INJ_LINEZOLIDE_600MG', 'Linezolide', 'INJECTION', 'FL', '600mg', 'FL', FALSE, NULL, 49),
    ('INJ_LIPOFUNDINE_500ML', 'Lipofundine', 'INJECTION', 'FL', '500ml', 'FL', FALSE, NULL, 50),
    ('INJ_LOVENOX_0_4ML', 'Lovenox', 'INJECTION', 'FL', '0.4ml', 'FL', FALSE, NULL, 51),
    ('INJ_LOVENOX_0_6ML', 'Lovenox', 'INJECTION', 'FL', '0.6ml', 'FL', FALSE, NULL, 52),
    ('INJ_MAGNESIUM_AMPOULE_2ML', 'Magnesium ampoule', 'INJECTION', 'AMP', '2ml', 'Amp', FALSE, NULL, 53),
    ('INJ_MANNITOL_0_2', 'Mannitol', 'INJECTION', 'FL', '0.2', 'FL', FALSE, NULL, 54),
    ('INJ_MERONEM_1G', 'Meronem', 'INJECTION', 'FL', '1g', 'FL', FALSE, NULL, 55),
    ('INJ_METOCLOPRAMIDE_10MG', 'Metoclopramide', 'INJECTION', 'AMP', '10mg', 'Amp', FALSE, NULL, 56),
    ('INJ_M_TRONIDAZOLE_100ML', 'Métronidazole', 'INJECTION', 'FL', '100ml', 'FL', FALSE, NULL, 57),
    ('INJ_MIDAZOLAM_5MG', 'Midazolam', 'INJECTION', 'AMP', '5mg', 'Amp', FALSE, NULL, 58),
    ('INJ_MORPHINE_10MG', 'Morphine', 'INJECTION', 'AMP', '10mg', 'អំពូល', TRUE, '101', 59),
    ('INJ_MOXIFLOXACINE_500ML', 'Moxifloxacine', 'INJECTION', 'FL', '500ml', 'FL', FALSE, NULL, 60),
    ('INJ_NACL_2G', 'NaCl', 'INJECTION', 'AMP', '2g', 'Amp', FALSE, NULL, 61),
    ('INJ_NACL_4G', 'NaCl', 'INJECTION', 'AMP', '4g', 'Amp', FALSE, NULL, 62),
    ('INJ_NICARDIPINE_10MG', 'Nicardipine', 'INJECTION', 'AMP', '10mg', 'Amp', FALSE, NULL, 63),
    ('INJ_NITROGLYCERIN_50MG', 'Nitroglycerin', 'INJECTION', 'AMP', '50mg', 'Amp', FALSE, NULL, 64),
    ('INJ_NORADRENALINE_2MG', 'Noradrenaline', 'INJECTION', 'AMP', '2mg', 'Amp', FALSE, NULL, 65),
    ('INJ_NORADRENALINE_8MG', 'Noradrenaline', 'INJECTION', 'AMP', '8mg', 'Amp', FALSE, NULL, 66),
    ('INJ_NORCURON_10MG', 'Norcuron', 'INJECTION', 'FL', '10mg', 'FL', FALSE, NULL, 67),
    ('INJ_NORMACOL', 'Normacol', 'INJECTION', 'GEL', NULL, 'Gel', FALSE, NULL, 68),
    ('INJ_OCTREOTIDE_1ML', 'Octreotide', 'INJECTION', 'AMP', '1ml', 'Amp', FALSE, NULL, 69),
    ('INJ_OMEPRAZOL_40MG', 'Omeprazol', 'INJECTION', 'FL', '40mg', 'FL', FALSE, NULL, 70),
    ('INJ_PARAC_TAMOL_300MG', 'Paracétamol', 'INJECTION', 'FL', '300mg', 'FL', FALSE, NULL, 71),
    ('INJ_PARAC_TAMOL_1G', 'Paracétamol', 'INJECTION', 'FL', '1g', 'FL', FALSE, NULL, 72),
    ('INJ_PENICILLINE_1G', 'Penicilline', 'INJECTION', 'FL', '1g', 'FL', FALSE, NULL, 73),
    ('INJ_PLASMA_SUBSTITUTE_500ML', 'Plasma Substitute', 'INJECTION', 'FL', '500ml', 'FL', FALSE, NULL, 74),
    ('INJ_POTASSIUM_CHLORIDE_1G', 'Potassium chloride', 'INJECTION', 'AMP', '1g', 'Amp', FALSE, NULL, 75),
    ('INJ_POVIDONE_IODINE_0_1', 'Povidone Iodine', 'INJECTION', 'SOLUTION', '0.1', 'Solution', FALSE, NULL, 76),
    ('INJ_PROPOFOL_200ML', 'Propofol', 'INJECTION', 'FL', '200ml', 'FL', FALSE, NULL, 77),
    ('INJ_SALBUTAMOL_SPRAY', 'Salbutamol Spray', 'INJECTION', 'AEROSOL', NULL, 'Aerosol', FALSE, NULL, 78),
    ('INJ_SALBUTAMOL_NEBULISER_1ML', 'Salbutamol Nebuliser', 'INJECTION', 'AMP', '1ml', 'Amp', FALSE, NULL, 79),
    ('INJ_SANDOSTATINE_1ML', 'Sandostatine', 'INJECTION', 'AMP', '1ml', 'Amp', FALSE, NULL, 80),
    ('INJ_SERUM_DEXTROSE_500ML', 'Serum Dextrose ½', 'INJECTION', 'FL', '500ml', 'FL', FALSE, NULL, 81),
    ('INJ_SERUM_DEXTROSE_5_500ML', 'Serum Dextrose 5%', 'INJECTION', 'FL', '500ml', 'FL', FALSE, NULL, 82),
    ('INJ_SERUM_DEXTROSE_10_500ML', 'Serum Dextrose 10%', 'INJECTION', 'FL', '500ml', 'FL', FALSE, NULL, 83),
    ('INJ_SERUM_LACTATE_500ML', 'Serum Lactate', 'INJECTION', 'FL', '500ml', 'FL', FALSE, NULL, 84),
    ('INJ_SERUM_LACTATE_1000ML', 'Serum Lactate', 'INJECTION', 'FL', '1000ml', 'FL', FALSE, NULL, 85),
    ('INJ_SERUM_SALE_0_9_100ML', 'Serum Sale 0,9%', 'INJECTION', 'FL', '100ml', 'FL', FALSE, NULL, 86),
    ('INJ_S_RUM_SALE_0_9_500ML', 'Sérum Sale 0,9%', 'INJECTION', 'FL', '500ml', 'FL', FALSE, NULL, 87),
    ('INJ_S_RUM_SALE_0_9_1000ML', 'Sérum Sale 0,9%', 'INJECTION', 'FL', '1000ml', 'FL', FALSE, NULL, 88),
    ('INJ_SOLUMEDROL_125MG', 'Solumedrol', 'INJECTION', 'FL', '125mg', 'FL', FALSE, NULL, 89),
    ('INJ_SPASFON', 'Spasfon', 'INJECTION', 'AMP', NULL, 'Amp', FALSE, NULL, 90),
    ('INJ_SUXAMETHAONIUM_100MG', 'Suxamethaonium', 'INJECTION', 'AMP', '100mg', 'Amp', FALSE, NULL, 91),
    ('INJ_TANGANIL_500MG', 'Tanganil', 'INJECTION', 'AMP', '500mg', 'Amp', FALSE, NULL, 92),
    ('INJ_TAZINE_4_5G', 'Tazine', 'INJECTION', 'FL', '4,5g', 'FL', FALSE, NULL, 93),
    ('INJ_THIOPENTAL_1G', 'Thiopental', 'INJECTION', 'FL', '1g', 'FL', FALSE, NULL, 94),
    ('INJ_TRAMADOL_AMPOULE_100MG', 'Tramadol ampoule', 'INJECTION', 'AMP', '100mg', 'Amp', FALSE, NULL, 95),
    ('INJ_TRANEXAMIC_ACID_500MG', 'Tranexamic Acid', 'INJECTION', 'AMP', '500mg', 'Amp', FALSE, NULL, 96),
    ('INJ_VANCOMYCINE_500MG', 'Vancomycine', 'INJECTION', 'FL', '500mg', 'FL', FALSE, NULL, 97),
    ('INJ_VANCOMYCINE_1G', 'Vancomycine', 'INJECTION', 'FL', '1g', 'FL', FALSE, NULL, 98),
    ('INJ_VITAMINE_B1', 'Vitamine B1', 'INJECTION', 'AMP', NULL, 'Amp', FALSE, NULL, 99),
    ('INJ_VITAMINE_C_1G', 'Vitamine C', 'INJECTION', 'AMP', '1g', 'Amp', FALSE, NULL, 100),
    ('INJ_VITAMINE_K1_100MG', 'Vitamine K1', 'INJECTION', 'AMP', '100mg', 'Amp', FALSE, NULL, 101),
    ('INJ_XYLOCAINE_GEL_2', 'Xylocaine Gel', 'INJECTION', 'FL', '2%', 'FL', FALSE, NULL, 102)
ON CONFLICT (code) DO NOTHING;

COMMIT;
