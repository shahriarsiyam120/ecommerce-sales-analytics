"""Clean the three source CSVs without changing their inputs."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INPUT_DIR = PROJECT_ROOT / "data" / "sample"
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed"
REPORT_PATH = OUTPUT_DIR / "cleaning_report.json"

# Keep the project root importable when this file is launched directly.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.validation.data_validator import validate_dataframes  # noqa: E402

INPUT_FILES = {
    "customers": "customers.csv",
    "products": "products.csv",
    "orders": "orders.csv",
}
NULL_MARKERS = {"", "na", "n/a", "null", "none", "nan"}


class CleaningInputError(Exception):
    """Raised when a required source file cannot be read."""


def load_source_data(input_dir: Path = INPUT_DIR) -> dict[str, pd.DataFrame]:
    """Read the source files as strings, preserving IDs and malformed values."""
    datasets = {}
    for name, filename in INPUT_FILES.items():
        path = input_dir / filename
        if not path.is_file():
            raise CleaningInputError(f"Required input file does not exist: {path}")
        try:
            datasets[name] = pd.read_csv(path, dtype="string", keep_default_na=False)
        except (OSError, pd.errors.ParserError, UnicodeDecodeError) as exc:
            raise CleaningInputError(f"Could not read {path}: {exc}") from exc
    return datasets


def summarize_frame(frame: pd.DataFrame) -> dict[str, Any]:
    """Return a compact quality summary for one dataframe."""
    return {
        "row_count": int(len(frame)),
        "column_count": int(len(frame.columns)),
        "missing_values": {
            str(column): int(count)
            for column, count in frame.isna().sum().items()
            if count > 0
        },
        "duplicate_rows": int(frame.duplicated().sum()),
    }


def _normalize_missing_values(frame: pd.DataFrame, transformations: list[str]) -> pd.DataFrame:
    """Convert blank and common textual null markers to pandas missing values."""
    result = frame.copy()
    count = 0
    for column in result.select_dtypes(include=["object", "string"]).columns:
        values = result[column].astype("string").str.strip()
        missing_mask = values.str.casefold().isin(NULL_MARKERS)
        count += int(missing_mask.sum())
        result[column] = values.mask(missing_mask, pd.NA)
    transformations.append(f"Standardized blank/common null markers to missing values ({count} cells)")
    return result


def _trim_text(frame: pd.DataFrame, columns: list[str], transformations: list[str]) -> pd.DataFrame:
    result = frame.copy()
    changed = 0
    for column in columns:
        if column in result.columns:
            original = result[column].astype("string")
            trimmed = original.str.strip()
            changed += int((original.fillna("") != trimmed.fillna("")).sum())
            result[column] = trimmed
    transformations.append(f"Trimmed surrounding whitespace in {', '.join(columns)} ({changed} values changed)")
    return result


def _normalize_category(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    result = frame.copy()
    if column in result.columns:
        result[column] = result[column].astype("string").str.strip().str.title()
        if column == "payment_method":
            result[column] = result[column].replace({"Paypal": "PayPal"})
    return result


def _remove_exact_duplicates(frame: pd.DataFrame, transformations: list[str]) -> tuple[pd.DataFrame, int]:
    before = len(frame)
    result = frame.drop_duplicates(keep="first").copy()
    removed = before - len(result)
    transformations.append(f"Removed {removed} exact duplicate row(s); first occurrence retained")
    return result, removed


def clean_customers(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[str], int]:
    transformations: list[str] = []
    result = frame.copy()
    result, removed = _remove_exact_duplicates(result, transformations)
    result = _normalize_missing_values(result, transformations)
    text_columns = ["customer_id", "customer_name", "customer_email", "customer_region", "customer_city", "customer_segment"]
    result = _trim_text(result, text_columns, transformations)
    for column in ["customer_region", "customer_city", "customer_segment"]:
        result = _normalize_category(result, column)
    transformations.append("Normalized customer region, city, and segment to title case")
    if "signup_date" in result.columns:
        result["signup_date"] = pd.to_datetime(result["signup_date"], errors="coerce", format="mixed")
        transformations.append("Converted signup_date to datetime; unparseable values become missing")
    transformations.append("Preserved customer IDs and all nonduplicate records; no personal data was invented")
    return result, transformations, removed


def clean_products(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[str], int]:
    transformations: list[str] = []
    result = frame.copy()
    result, removed = _remove_exact_duplicates(result, transformations)
    result = _normalize_missing_values(result, transformations)
    text_columns = ["product_id", "product_name", "category", "subcategory"]
    result = _trim_text(result, text_columns, transformations)
    for column in ["product_name", "category", "subcategory"]:
        result = _normalize_category(result, column)
    transformations.append("Normalized product name, category, and subcategory to title case")
    for column in ["unit_cost", "unit_price"]:
        if column in result.columns:
            result[column] = pd.to_numeric(result[column], errors="coerce")
    transformations.append("Converted unit_cost and unit_price to numeric; invalid values become missing")
    transformations.append("Retained invalid prices and duplicate IDs for review; no product records were silently discarded")
    return result, transformations, removed


def clean_orders(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[str], int]:
    transformations: list[str] = []
    result = frame.copy()
    result, removed = _remove_exact_duplicates(result, transformations)
    result = _normalize_missing_values(result, transformations)
    text_columns = ["order_id", "customer_id", "product_id", "payment_method", "order_status"]
    result = _trim_text(result, text_columns, transformations)
    for column in ["payment_method", "order_status"]:
        result = _normalize_category(result, column)
    transformations.append("Normalized payment_method and order_status to title case")
    if "order_date" in result.columns:
        result["order_date"] = pd.to_datetime(result["order_date"], errors="coerce", format="mixed")
        transformations.append("Converted order_date to datetime; unparseable values become missing")
    if "quantity" in result.columns:
        result["quantity"] = pd.to_numeric(result["quantity"], errors="coerce")
        # Preserve fractional values so invalid quantities are visible to validation.
        transformations.append("Converted quantity to numeric; invalid values become missing")
    if "discount" in result.columns:
        result["discount"] = pd.to_numeric(result["discount"], errors="coerce")
        transformations.append("Converted discount to numeric; invalid values become missing")
    transformations.append("Retained invalid quantities, discounts, and references for review; no order records were silently discarded")
    return result, transformations, removed


def add_sales_columns(orders: pd.DataFrame, products: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Join unit prices by product ID and derive gross, discount, and net sales."""
    result = orders.copy()
    transformations = []
    if not {"product_id", "unit_price"}.issubset(products.columns):
        price_by_product: dict[str, float] = {}
    else:
        # Ambiguous IDs are not assigned an arbitrary price; validation reports them.
        duplicate_ids = products["product_id"].duplicated(keep=False)
        usable = products.loc[~duplicate_ids & products["product_id"].notna()]
        price_by_product = usable.set_index("product_id")["unit_price"].to_dict()
    unit_price = pd.to_numeric(result.get("product_id", pd.Series(index=result.index, dtype="string")).map(price_by_product), errors="coerce")
    quantity = pd.to_numeric(result.get("quantity"), errors="coerce")
    discount = pd.to_numeric(result.get("discount"), errors="coerce")
    result["gross_sales"] = quantity * unit_price
    result["discount_amount"] = result["gross_sales"] * discount
    result["net_sales"] = result["gross_sales"] - result["discount_amount"]
    transformations.append("Looked up product unit_price by product_id without adding product cost to orders")
    transformations.append("Calculated gross_sales = quantity × unit_price")
    transformations.append("Calculated discount_amount = quantity × unit_price × discount")
    transformations.append("Calculated net_sales = gross_sales − discount_amount")
    transformations.append("No profit calculation performed because order-level product cost is unavailable")
    return result, transformations


def clean_datasets(datasets: dict[str, pd.DataFrame]) -> tuple[dict[str, pd.DataFrame], dict[str, dict[str, Any]]]:
    """Clean each dataset and create before/after and action reports."""
    cleaners = {"customers": clean_customers, "products": clean_products, "orders": clean_orders}
    cleaned: dict[str, pd.DataFrame] = {}
    details: dict[str, dict[str, Any]] = {}
    for name, cleaner in cleaners.items():
        source = datasets[name]
        before = summarize_frame(source)
        cleaned_frame, transformations, removed = cleaner(source)
        after = summarize_frame(cleaned_frame)
        details[name] = {
            "input_rows": before["row_count"],
            "output_rows": after["row_count"],
            "rows_removed": removed,
            "missing_values_before": before["missing_values"],
            "missing_values_after": after["missing_values"],
            "summary_before": before,
            "summary_after": after,
            "transformations_performed": transformations,
            "records_rejected_or_excluded": {
                "count": removed,
                "rule": "Exact duplicate rows were removed with the first occurrence retained; no other records were rejected.",
            },
        }
        cleaned[name] = cleaned_frame

    cleaned["orders"], financial_transformations = add_sales_columns(cleaned["orders"], cleaned["products"])
    details["orders"]["transformations_performed"].extend(financial_transformations)
    details["orders"]["summary_after"] = summarize_frame(cleaned["orders"])
    details["orders"]["missing_values_after"] = details["orders"]["summary_after"]["missing_values"]
    return cleaned, details


def write_cleaned_data(cleaned: dict[str, pd.DataFrame], output_dir: Path = OUTPUT_DIR) -> None:
    """Write processed outputs only; source data is never opened for writing."""
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, frame in cleaned.items():
        frame.to_csv(output_dir / f"{name}_cleaned.csv", index=False, date_format="%Y-%m-%d")


def run_cleaning(input_dir: Path = INPUT_DIR, output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    """Run the full cleaning process, save outputs/report, and validate outputs."""
    source_data = load_source_data(input_dir)
    cleaned, details = clean_datasets(source_data)
    write_cleaned_data(cleaned, output_dir)
    processed_data = {
        name: pd.read_csv(output_dir / f"{name}_cleaned.csv", dtype="string")
        for name in INPUT_FILES
    }
    validation = validate_dataframes(processed_data)
    report = {
        "input_directory": str(input_dir),
        "output_directory": str(output_dir),
        "datasets": details,
        "processed_validation": validation,
        "validation_status": "FAIL" if any(item["validation_status"] == "FAIL" for item in validation.values()) else (
            "WARNING" if any(item["validation_status"] == "WARNING" for item in validation.values()) else "PASS"
        ),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / REPORT_PATH.name).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def _print_summary(report: dict[str, Any]) -> None:
    print("Data cleaning summary")
    for name, detail in report["datasets"].items():
        before = detail["summary_before"]
        after = detail["summary_after"]
        before_missing = sum(before["missing_values"].values())
        after_missing = sum(after["missing_values"].values())
        print(
            f"{name:<10} rows {detail['input_rows']:,} to {detail['output_rows']:,} "
            f"(removed {detail['rows_removed']:,} exact duplicates); "
            f"missing {before_missing} to {after_missing}; "
            f"duplicates {before['duplicate_rows']} to {after['duplicate_rows']}"
        )
    print(f"Processed validation: {report['validation_status']}")
    for name, result in report["processed_validation"].items():
        print(f"  {result['validation_status']:<7} {name}")
    print(f"Cleaning report: {OUTPUT_DIR / REPORT_PATH.name}")


def main() -> int:
    try:
        report = run_cleaning()
    except (CleaningInputError, OSError, ValueError, KeyError) as exc:
        print(f"Cleaning failed: {exc}", file=sys.stderr)
        return 1
    _print_summary(report)
    return 1 if report["validation_status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
