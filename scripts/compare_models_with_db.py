"""
scripts/compare_models_with_db.py
=================================
Compares SQLAlchemy models defined in app/models against the active database schema.
Identifies:
  - Schemas defined in models but missing in the database (and vice versa).
  - Tables defined in models but missing in the database.
  - Tables existing in the database but missing in models.
  - Columns defined in models but missing in the database.
  - Columns existing in the database but missing in models.
  - (Optional) Data type and nullability differences.

Usage:
  # Basic run against all active schemas
  python scripts/compare_models_with_db.py

  # Filter by specific schema
  python scripts/compare_models_with_db.py --schema auth

  # Check column types and nullability drift
  python scripts/compare_models_with_db.py --check-types

  # Save markdown report
  python scripts/compare_models_with_db.py --output-markdown comparison_report.md
"""

import argparse
from dataclasses import asdict, dataclass, field
import importlib
import json
from pathlib     import Path
import sys
from typing      import Any, Dict, List, Optional, Set, Tuple

# Ensure project root is in sys.path and filter foreign 'khmer' entry before importing application modules
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path     = [p for p in sys.path if 'khmer' not in p.lower()]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy        import inspect
from sqlalchemy.engine import Engine, Inspector
from sqlalchemy.schema import Column, Table

from app.core.db           import engine
from app.models.base_model import Base

# Statically import all known models to satisfy top-level import rules
import app.models.auth_model
import app.models.base_data_model
import app.models.data_model
import app.models.track_model


@dataclass
class ColumnDifference:
    column_name       : str
    model_type        : Optional[str]  = None
    database_type     : Optional[str]  = None
    model_nullable    : Optional[bool] = None
    database_nullable : Optional[bool] = None
    notes             : Optional[str]  = None


@dataclass
class TableComparisonResult:
    schema_name                 : str
    table_name                  : str
    exists_in_model             : bool
    exists_in_database          : bool
    missing_columns_in_database : List[Dict[str, Any]]   = field(default_factory=list)
    missing_columns_in_model    : List[Dict[str, Any]]   = field(default_factory=list)
    type_mismatches             : List[ColumnDifference] = field(default_factory=list)


@dataclass
class AuditSummary:
    total_model_schemas               : int       = 0
    total_database_schemas            : int       = 0
    missing_schemas_in_database       : List[str] = field(default_factory=list)
    missing_schemas_in_model          : List[str] = field(default_factory=list)
    total_model_tables                : int       = 0
    total_database_tables             : int       = 0
    missing_tables_in_database        : List[str] = field(default_factory=list)
    missing_tables_in_model           : List[str] = field(default_factory=list)
    tables_with_missing_columns       : List[str] = field(default_factory=list)
    total_missing_columns_in_database : int       = 0
    total_missing_columns_in_model    : int       = 0


class ModelDatabaseComparator:
    """Compares registered SQLAlchemy models with active database schema."""

    SYSTEM_SCHEMAS: Set[str] = {
        'information_schema'
        , 'pg_catalog'
        , 'pg_toast'
    }


    def __init__(self, database_engine: Engine) -> None:
        self.database_engine : Engine    = database_engine
        self.inspector       : Inspector = inspect(database_engine)


    def discover_additional_models(self) -> None:
        """Dynamically load any newly added model files in app/models."""
        models_directory = PROJECT_ROOT / 'app' / 'models'
        if not models_directory.exists():
            return

        for model_file in models_directory.glob('*.py'):
            if model_file.name in ('base_model.py', '__init__.py'):
                continue
            module_name = f'app.models.{model_file.stem}'
            if module_name not in sys.modules:
                try:
                    importlib.import_module(module_name)
                except Exception as import_error:
                    print(f'Warning: Failed to import {module_name}: {import_error}')


    def fetch_model_schemas(
        self
        , target_schema: Optional[str] = None
    ) -> Set[str]:
        """Collect all schemas defined in Base.metadata."""
        schemas: Set[str] = set()
        for _, table in Base.metadata.tables.items():
            schema_name = table.schema or 'public'
            if target_schema and schema_name.lower() != target_schema.lower():
                continue
            schemas.add(schema_name)
        return schemas


    def fetch_database_schemas(
        self
        , target_schema: Optional[str] = None
    ) -> Set[str]:
        """Fetch all non-system schemas from the database."""
        all_schemas = self.inspector.get_schema_names()
        schemas = {
            schema_name
            for schema_name in all_schemas
            if schema_name not in self.SYSTEM_SCHEMAS
        }
        if target_schema:
            schemas = {s for s in schemas if s.lower() == target_schema.lower()}
        return schemas


    def fetch_model_tables(
        self
        , target_schema : Optional[str] = None
        , target_table  : Optional[str] = None
    ) -> Dict[Tuple[str, str], Table]:
        """Collect all tables defined in Base.metadata."""
        model_tables: Dict[Tuple[str, str], Table] = {}

        for full_name, table in Base.metadata.tables.items():
            schema_name = table.schema or 'public'
            table_name  = table.name

            if target_schema and schema_name.lower() != target_schema.lower():
                continue
            if target_table and table_name.lower() != target_table.lower():
                continue

            model_tables[(schema_name, table_name)] = table

        return model_tables


    def fetch_database_tables(
        self
        , target_schema: Optional[str] = None
    ) -> Dict[Tuple[str, str], List[Dict[str, Any]]]:
        """Fetch all tables and their columns from the database."""
        database_tables: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}

        if target_schema:
            candidate_schemas = [target_schema]
        else:
            all_schemas = self.inspector.get_schema_names()
            candidate_schemas = [
                schema_name
                for schema_name in all_schemas
                if schema_name not in self.SYSTEM_SCHEMAS
            ]

        for schema_name in candidate_schemas:
            try:
                table_names = self.inspector.get_table_names(schema=schema_name)
            except Exception as inspection_error:
                print(f'Warning: Could not list tables in schema {schema_name}: {inspection_error}')
                continue

            for table_name in table_names:
                try:
                    columns = self.inspector.get_columns(
                        table_name = table_name
                        , schema   = schema_name
                    )
                    database_tables[(schema_name, table_name)] = columns
                except Exception as column_error:
                    print(f'Warning: Could not get columns for {schema_name}.{table_name}: {column_error}')
                    database_tables[(schema_name, table_name)] = []

        return database_tables


    def compare(
        self
        , target_schema : Optional[str] = None
        , target_table  : Optional[str] = None
        , check_types   : bool          = False
    ) -> List[TableComparisonResult]:
        """Execute full comparison between models and database."""
        self.discover_additional_models()

        model_tables    = self.fetch_model_tables(
            target_schema  = target_schema
            , target_table = target_table
        )
        database_tables = self.fetch_database_tables(
            target_schema = target_schema
        )

        all_keys: Set[Tuple[str, str]] = set(model_tables.keys()) | set(database_tables.keys())
        if target_table:
            all_keys = {key for key in all_keys if key[1].lower() == target_table.lower()}

        comparison_results: List[TableComparisonResult] = []

        for schema_name, table_name in sorted(all_keys):
            key                = (schema_name, table_name)
            exists_in_model    = key in model_tables
            exists_in_database = key in database_tables

            missing_in_database : List[Dict[str, Any]]   = []
            missing_in_model    : List[Dict[str, Any]]   = []
            type_mismatches     : List[ColumnDifference] = []

            if exists_in_model and exists_in_database:
                table_definition = model_tables[key]
                database_columns = database_tables[key]

                model_column_map: Dict[str, Column] = {
                    column.name: column
                    for column in table_definition.columns
                }
                database_column_map: Dict[str, Dict[str, Any]] = {
                    column_metadata['name']: column_metadata
                    for column_metadata in database_columns
                }

                # Check columns defined in model but missing in DB
                for column_name, column_object in model_column_map.items():
                    if column_name not in database_column_map:
                        missing_in_database.append({
                            'name'          : column_name
                            , 'type'        : str(column_object.type)
                            , 'nullable'    : column_object.nullable
                            , 'primary_key' : column_object.primary_key
                        })

                # Check columns present in DB but missing in model
                for column_name, column_metadata in database_column_map.items():
                    if column_name not in model_column_map:
                        missing_in_model.append({
                            'name'       : column_name
                            , 'type'     : str(column_metadata.get('type', 'UNKNOWN'))
                            , 'nullable' : column_metadata.get('nullable', True)
                            , 'default'  : str(column_metadata.get('default', ''))
                        })

                # Check optional type and nullability differences
                if check_types:
                    for column_name in sorted(set(model_column_map.keys()) & set(database_column_map.keys())):
                        column_object   = model_column_map[column_name]
                        column_metadata = database_column_map[column_name]

                        model_type_string = str(column_object.type).upper()
                        database_type_str = str(column_metadata.get('type', '')).upper()

                        model_nullable    = bool(column_object.nullable)
                        database_nullable = bool(column_metadata.get('nullable', True))

                        notes: List[str] = []
                        if model_nullable != database_nullable:
                            notes.append(
                                f'Nullable mismatch (Model: {model_nullable}, DB: {database_nullable})'
                            )

                        if notes:
                            type_mismatches.append(
                                ColumnDifference(
                                    column_name         = column_name
                                    , model_type        = model_type_string
                                    , database_type     = database_type_str
                                    , model_nullable    = model_nullable
                                    , database_nullable = database_nullable
                                    , notes             = '; '.join(notes)
                                )
                            )

            comparison_results.append(
                TableComparisonResult(
                    schema_name                   = schema_name
                    , table_name                  = table_name
                    , exists_in_model             = exists_in_model
                    , exists_in_database          = exists_in_database
                    , missing_columns_in_database = missing_in_database
                    , missing_columns_in_model    = missing_in_model
                    , type_mismatches             = type_mismatches
                )
            )

        return comparison_results


    def compute_summary(
        self
        , results       : List[TableComparisonResult]
        , target_schema : Optional[str] = None
    ) -> AuditSummary:
        """Calculate executive statistics across all comparison results."""
        summary          = AuditSummary()
        model_schemas    = self.fetch_model_schemas(target_schema=target_schema)
        database_schemas = self.fetch_database_schemas(target_schema=target_schema)

        summary.total_model_schemas         = len(model_schemas)
        summary.total_database_schemas      = len(database_schemas)
        summary.missing_schemas_in_database = sorted(model_schemas - database_schemas)
        summary.missing_schemas_in_model    = sorted(database_schemas - model_schemas)

        for result in results:
            if result.exists_in_model:
                summary.total_model_tables += 1
            if result.exists_in_database:
                summary.total_database_tables += 1

            full_table_name = f'{result.schema_name}.{result.table_name}'

            if result.exists_in_model and not result.exists_in_database:
                summary.missing_tables_in_database.append(full_table_name)
            elif result.exists_in_database and not result.exists_in_model:
                summary.missing_tables_in_model.append(full_table_name)

            has_column_discrepancies = bool(
                result.missing_columns_in_database or result.missing_columns_in_model
            )
            if has_column_discrepancies:
                summary.tables_with_missing_columns.append(full_table_name)
                summary.total_missing_columns_in_database += len(result.missing_columns_in_database)
                summary.total_missing_columns_in_model    += len(result.missing_columns_in_model)

        return summary


    def print_terminal_report(
        self
        , results       : List[TableComparisonResult]
        , check_types   : bool          = False
        , target_schema : Optional[str] = None
    ) -> None:
        """Print a structured, clean terminal report."""
        if hasattr(sys.stdout, 'reconfigure'):
            try:
                sys.stdout.reconfigure(encoding='utf-8')
            except Exception:
                pass

        summary = self.compute_summary(results=results, target_schema=target_schema)

        line_separator = '=' * 80
        thin_separator = '-' * 80

        print()
        print(line_separator)
        print('  MSM API — Model vs Database Schema Comparison Report')
        print(line_separator)
        print(f'  Total Schemas in Models         : {summary.total_model_schemas}')
        print(f'  Total Schemas in Database       : {summary.total_database_schemas}')
        print(f'  Schemas Missing in DB           : {len(summary.missing_schemas_in_database)}')
        print(f'  Total Tables in Models          : {summary.total_model_tables}')
        print(f'  Total Tables in Database        : {summary.total_database_tables}')
        print(f'  Tables Missing in DB            : {len(summary.missing_tables_in_database)}')
        print(f'  Tables Missing in Models        : {len(summary.missing_tables_in_model)}')
        print(f'  Tables with Column Drift        : {len(summary.tables_with_missing_columns)}')
        print(f'  Total Columns Missing in DB     : {summary.total_missing_columns_in_database}')
        print(f'  Total Columns Missing in Models : {summary.total_missing_columns_in_model}')
        print(line_separator)

        # 0. Missing Schemas in DB
        if summary.missing_schemas_in_database:
            print('\n[!] SCHEMAS DEFINED IN MODELS BUT MISSING IN DATABASE:')
            for schema_name in summary.missing_schemas_in_database:
                print(f'  [-] {schema_name}')
        else:
            print('\n[OK] All model schemas exist in the database.')

        # 1. Missing Tables in DB
        if summary.missing_tables_in_database:
            print('\n[!] TABLES DEFINED IN MODELS BUT MISSING IN DATABASE:')
            for table_name in summary.missing_tables_in_database:
                print(f'  [-] {table_name}')
        else:
            print('\n[OK] All model tables exist in the database.')

        # 2. Missing Tables in Models
        if summary.missing_tables_in_model:
            print('\n[i] TABLES IN DATABASE BUT NOT DEFINED IN MODELS:')
            for table_name in summary.missing_tables_in_model:
                print(f'  [+] {table_name}')

        # 3. Column Discrepancies
        if summary.tables_with_missing_columns:
            print('\n[!] COLUMN DISCREPANCIES IN MATCHING TABLES:')
            print(thin_separator)
            for result in results:
                if not (result.missing_columns_in_database or result.missing_columns_in_model):
                    continue

                full_name = f'{result.schema_name}.{result.table_name}'
                print(f'\nTable: {full_name}')

                if result.missing_columns_in_database:
                    print('  Missing in Database (Defined in Model):')
                    for column_item in result.missing_columns_in_database:
                        nullable_label    = 'NULL' if column_item['nullable'] else 'NOT NULL'
                        primary_key_label = ' [PK]' if column_item.get('primary_key') else ''
                        print(
                            f"    [-] {column_item['name']} ({column_item['type']}, {nullable_label}{primary_key_label})"
                        )

                if result.missing_columns_in_model:
                    print('  Missing in Model (Exists in Database):')
                    for column_item in result.missing_columns_in_model:
                        nullable_label      = 'NULL' if column_item['nullable'] else 'NOT NULL'
                        default_value_label = (
                            f" default={column_item['default']}"
                            if column_item.get('default')
                            else ''
                        )
                        print(
                            f"    [+] {column_item['name']} ({column_item['type']}, {nullable_label}{default_value_label})"
                        )
        else:
            print('\n[OK] No missing columns detected in matching tables.')

        # 4. Optional Type / Nullability Mismatches
        if check_types:
            tables_with_type_mismatches = [
                result for result in results if result.type_mismatches
            ]
            if tables_with_type_mismatches:
                print('\n[i] COLUMN ATTRIBUTE (NULLABILITY/TYPE) MISMATCHES:')
                print(thin_separator)
                for result in tables_with_type_mismatches:
                    full_name = f'{result.schema_name}.{result.table_name}'
                    print(f'\nTable: {full_name}')
                    for difference in result.type_mismatches:
                        print(f'  [*] {difference.column_name}: {difference.notes}')
            else:
                print('\n[OK] No nullability mismatches detected.')

        print()
        print(line_separator)
        if (
            not summary.missing_schemas_in_database
            and not summary.missing_tables_in_database
            and not summary.tables_with_missing_columns
        ):
            print('  RESULT: [PASSED] Models match database columns with zero missing attributes.')
        else:
            print('  RESULT: [ACTION REQUIRED] Schema drift detected between models and database.')
        print(line_separator)
        print()


    def export_markdown_report(
        self
        , results       : List[TableComparisonResult]
        , file_path     : Path
        , check_types   : bool          = False
        , target_schema : Optional[str] = None
    ) -> None:
        """Generate and save a detailed Markdown audit report."""
        summary = self.compute_summary(results=results, target_schema=target_schema)

        lines: List[str] = [
            '# Database vs SQLAlchemy Models Comparison Report'
            , ''
            , f'Generated at: {PROJECT_ROOT.name}'
            , ''
            , '## Executive Summary'
            , ''
            , '| Metric | Value |'
            , '| --- | --- |'
            , f'| Total Model Schemas | {summary.total_model_schemas} |'
            , f'| Total Database Schemas | {summary.total_database_schemas} |'
            , f'| Schemas Missing in Database | {len(summary.missing_schemas_in_database)} |'
            , f'| Total Model Tables | {summary.total_model_tables} |'
            , f'| Total Database Tables | {summary.total_database_tables} |'
            , f'| Tables Missing in Database | {len(summary.missing_tables_in_database)} |'
            , f'| Tables Missing in Models | {len(summary.missing_tables_in_model)} |'
            , f'| Tables with Column Differences | {len(summary.tables_with_missing_columns)} |'
            , f'| Total Missing Columns in Database | {summary.total_missing_columns_in_database} |'
            , f'| Total Missing Columns in Models | {summary.total_missing_columns_in_model} |'
            , ''
        ]

        if summary.missing_tables_in_database:
            lines.extend([
                '## ❌ Tables in Models Missing in Database'
                , ''
                , '| Schema | Table Name |'
                , '| --- | --- |'
            ])
            for full_name in summary.missing_tables_in_database:
                schema_name, table_name = full_name.split('.', 1)
                lines.append(f'| `{schema_name}` | `{table_name}` |')
            lines.append('')

        if summary.missing_tables_in_model:
            lines.extend([
                '## ⚠️ Tables in Database Missing in Models'
                , ''
                , '| Schema | Table Name |'
                , '| --- | --- |'
            ])
            for full_name in summary.missing_tables_in_model:
                schema_name, table_name = full_name.split('.', 1)
                lines.append(f'| `{schema_name}` | `{table_name}` |')
            lines.append('')

        if summary.tables_with_missing_columns:
            lines.extend([
                '## ⚠️ Column Differences in Matching Tables'
                , ''
            ])
            for result in results:
                if not (result.missing_columns_in_database or result.missing_columns_in_model):
                    continue

                full_name = f'{result.schema_name}.{result.table_name}'
                lines.extend([
                    f'### `{full_name}`'
                    , ''
                ])

                if result.missing_columns_in_database:
                    lines.extend([
                        '**Missing in Database (Defined in Model):**'
                        , ''
                        , '| Column | Type | Nullable | Primary Key |'
                        , '| --- | --- | --- | --- |'
                    ])
                    for column_item in result.missing_columns_in_database:
                        lines.append(
                            f"| `{column_item['name']}` | `{column_item['type']}` | `{column_item['nullable']}` | `{column_item.get('primary_key', False)}` |"
                        )
                    lines.append('')

                if result.missing_columns_in_model:
                    lines.extend([
                        '**Missing in Model (Exists in Database):**'
                        , ''
                        , '| Column | Type | Nullable | Default |'
                        , '| --- | --- | --- | --- |'
                    ])
                    for column_item in result.missing_columns_in_model:
                        lines.append(
                            f"| `{column_item['name']}` | `{column_item['type']}` | `{column_item['nullable']}` | `{column_item.get('default', '')}` |"
                        )
                    lines.append('')

        file_path.write_text('\n'.join(lines), encoding='utf-8')
        print(f'Markdown report exported to: {file_path.resolve()}')


def main() -> None:
    parser = argparse.ArgumentParser(
        description = 'Compare SQLAlchemy models against active database schema.'
    )
    parser.add_argument(
        '--schema'
        , dest    = 'target_schema'
        , type    = str
        , default = None
        , help    = 'Filter comparison to a specific schema (e.g. auth, base_data, data, track)'
    )
    parser.add_argument(
        '--table'
        , dest    = 'target_table'
        , type    = str
        , default = None
        , help    = 'Filter comparison to a specific table name'
    )
    parser.add_argument(
        '--check-types'
        , dest    = 'check_types'
        , action  = 'store_true'
        , help    = 'Check column nullability and type mismatches'
    )
    parser.add_argument(
        '--output-markdown'
        , dest    = 'output_markdown'
        , type    = str
        , default = None
        , help    = 'Path to export report as a Markdown file'
    )
    parser.add_argument(
        '--json'
        , dest    = 'output_json'
        , action  = 'store_true'
        , help    = 'Output raw results in JSON format'
    )

    arguments = parser.parse_args()

    comparator = ModelDatabaseComparator(database_engine=engine)
    results    = comparator.compare(
        target_schema  = arguments.target_schema
        , target_table = arguments.target_table
        , check_types  = arguments.check_types
    )

    if arguments.output_json:
        serialized_results = [
            asdict(result)
            for result in results
        ]
        print(json.dumps(serialized_results, indent=2))
        return

    comparator.print_terminal_report(
        results         = results
        , check_types   = arguments.check_types
        , target_schema = arguments.target_schema
    )

    if arguments.output_markdown:
        comparator.export_markdown_report(
            results         = results
            , file_path     = Path(arguments.output_markdown)
            , check_types   = arguments.check_types
            , target_schema = arguments.target_schema
        )


if __name__ == '__main__':
    main()
