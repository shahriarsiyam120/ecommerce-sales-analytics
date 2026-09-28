"""Configuration-driven file/database ingestion and validated processing."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.analytics.advanced_analytics import run_advanced_analytics  # noqa: E402
from src.cleaning.data_cleaner import clean_datasets, write_cleaned_data  # noqa: E402
from src.validation.data_validator import (  # noqa: E402
    SCHEMAS,
    validate_dataframes,
)


class IngestionError(ValueError):
    """Raised when configured source data cannot be loaded or validated."""


def _read_file(path: Path, file_format: str, sheet_name: str | int | None) -> pd.DataFrame:
    if not path.is_file():
        raise IngestionError(f"Configured source file does not exist: {path}")
    try:
        if file_format == "csv":
            return pd.read_csv(path, dtype="string", keep_default_na=False)
        if file_format in {"xlsx", "xls", "excel"}:
            return pd.read_excel(
                path,
                sheet_name=0 if sheet_name is None else sheet_name,
                dtype="string",
                keep_default_na=False,
            )
        if file_format == "parquet":
            return pd.read_parquet(path)
    except ImportError as exc:
        raise IngestionError(
            f"Reading {file_format} requires an optional dependency: {exc}"
        ) from exc
    except (OSError, ValueError, pd.errors.ParserError) as exc:
        raise IngestionError(f"Could not read configured source {path}: {exc}") from exc
    raise IngestionError(f"Unsupported file format {file_format!r} for {path}")


def _read_mysql(dataset: dict[str, Any], database: dict[str, Any]) -> pd.DataFrame:
    table = str(dataset.get("table", ""))
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table):
        raise IngestionError(f"Invalid MySQL table name: {table!r}")
    environment_variable = str(database.get("url_env", "ECOMMERCE_DATABASE_URL"))
    connection_url = os.environ.get(environment_variable)
    if not connection_url:
        raise IngestionError(
            f"Set {environment_variable} to the database connection URL; "
            "do not put credentials in the config file."
        )
    try:
        from sqlalchemy import create_engine

        engine = create_engine(connection_url)
        try:
            return pd.read_sql_table(table, engine, schema=database.get("schema"))
        finally:
            engine.dispose()
    except ImportError as exc:
        raise IngestionError(
            "MySQL ingestion requires SQLAlchemy and a MySQL driver (for example, PyMySQL)."
        ) from exc
    except Exception as exc:
        raise IngestionError(
            f"Could not read MySQL table {table!r}; check the connection, "
            "permissions, and table name."
        ) from exc


def _standardize_text_columns(name: str, frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    for field in SCHEMAS[name].get("text", []):
        if field in result:
            result[field] = result[field].astype("string")
    return result


def load_configured_datasets(
    configuration: dict[str, Any], project_root: Path = PROJECT_ROOT
) -> dict[str, pd.DataFrame]:
    """Read configured sources and map source column names to internal names."""
    source_type = configuration.get("source_type", "files")
    entries = configuration.get("datasets", {})
    datasets: dict[str, pd.DataFrame] = {}
    for name in SCHEMAS:
        if name not in entries:
            raise IngestionError(f"Configuration is missing the {name!r} dataset entry")
        entry = entries[name]
        if source_type == "mysql":
            frame = _read_mysql(entry, configuration.get("database", {}))
        elif source_type == "files":
            source_path = Path(entry.get("path", ""))
            path = source_path if source_path.is_absolute() else project_root / source_path
            file_format = str(
                entry.get("format", configuration.get("default_format", "csv"))
            ).lower()
            frame = _read_file(path, file_format, entry.get("sheet_name"))
        else:
            raise IngestionError(
                f"Unsupported source_type {source_type!r}; expected 'files' or 'mysql'."
            )

        mapping = entry.get("column_mapping", {})
        if not isinstance(mapping, dict) or any(
            not isinstance(source, str) or not isinstance(target, str)
            for source, target in mapping.items()
        ):
            raise IngestionError(f"{name} column_mapping must map source column names to strings")
        if len(set(mapping.values())) != len(mapping):
            raise IngestionError(f"{name} column_mapping contains duplicate internal column names")
        frame = frame.rename(columns=mapping)
        if frame.columns.duplicated().any():
            duplicated = sorted(frame.columns[frame.columns.duplicated()].astype(str).unique())
            raise IngestionError(
                f"{name} column mapping creates duplicate columns: {', '.join(duplicated)}"
            )
        datasets[name] = _standardize_text_columns(name, frame)
    return datasets


def _validation_errors(reports: dict[str, dict[str, Any]]) -> list[str]:
    errors = []
    for name, report in reports.items():
        if report["validation_status"] != "FAIL":
            continue
        details = []
        if report["missing_columns"]:
            details.append(f"missing columns: {', '.join(report['missing_columns'])}")
        if report["missing_values"]:
            details.append(f"missing values: {report['missing_values']}")
        if report["duplicate_primary_keys"]:
            details.append(f"duplicate primary-key rows: {report['duplicate_primary_keys']}")
        if report["invalid_values"]:
            details.append(f"invalid values: {report['invalid_values']}")
        if report["foreign_key_violations"]:
            details.append(f"foreign-key violations: {report['foreign_key_violations']}")
        errors.append(f"{name}: {'; '.join(details)}")
    return errors


def run_configured_pipeline(
    configuration: dict[str, Any], project_root: Path = PROJECT_ROOT
) -> dict[str, Any]:
    """Validate raw inputs, clean them, validate outputs, then run analytics."""
    datasets = load_configured_datasets(configuration, project_root)
    accepted_categories = configuration.get("accepted_categories", {})
    raw_reports = validate_dataframes(datasets, accepted_categories=accepted_categories)
    raw_errors = _validation_errors(raw_reports)
    if raw_errors:
        raise IngestionError(
            "Source validation failed before cleaning:\n- " + "\n- ".join(raw_errors)
        )

    cleaned, cleaning_details = clean_datasets(datasets)
    output_value = Path(configuration.get("output_directory", "data/processed"))
    output_dir = output_value if output_value.is_absolute() else project_root / output_value
    write_cleaned_data(cleaned, output_dir)
    processed = {
        name: pd.read_csv(output_dir / f"{name}_cleaned.csv", dtype="string")
        for name in SCHEMAS
    }
    processed_reports = validate_dataframes(
        processed, accepted_categories=accepted_categories
    )
    processed_errors = _validation_errors(processed_reports)
    if processed_errors:
        raise IngestionError(
            "Processed validation failed after cleaning:\n- "
            + "\n- ".join(processed_errors)
        )

    cleaning_report = {
        "datasets": cleaning_details,
        "processed_validation": processed_reports,
        "validation_status": "PASS",
    }
    (output_dir / "cleaning_report.json").write_text(
        json.dumps(cleaning_report, indent=2), encoding="utf-8"
    )
    analytics_dir = output_dir / "analytics"
    analytics = run_advanced_analytics(output_dir, analytics_dir)
    return {
        "raw_validation": raw_reports,
        "processed_validation": processed_reports,
        "cleaning_details": cleaning_details,
        "analytics": analytics,
        "output_directory": output_dir,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="Path to a JSON data-source configuration")
    args = parser.parse_args()
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = PROJECT_ROOT / config_path
    try:
        configuration = json.loads(config_path.read_text(encoding="utf-8"))
        result = run_configured_pipeline(configuration)
    except (OSError, json.JSONDecodeError, IngestionError, ValueError, KeyError) as exc:
        print(f"Configured pipeline failed: {exc}", file=sys.stderr)
        return 1
    print(f"Raw validation: PASS ({len(result['raw_validation'])} datasets)")
    print(f"Processed validation: PASS ({len(result['processed_validation'])} datasets)")
    print(f"Processed outputs: {result['output_directory']}")
    print("Advanced analytics generated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())