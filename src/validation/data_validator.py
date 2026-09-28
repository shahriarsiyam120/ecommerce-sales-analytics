"""Reusable schema, value, and relationship checks for the sample CSV files."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data" / "sample"

SCHEMAS = {
    "customers": {
        "file": "customers.csv",
        "primary_key": "customer_id",
        "required": ["customer_id", "customer_name", "customer_email", "customer_region", "customer_city", "customer_segment", "signup_date"],
        "optional": [],
        "text": ["customer_id", "customer_name", "customer_email", "customer_region", "customer_city", "customer_segment"],
        "dates": ["signup_date"],
    },
    "products": {
        "file": "products.csv",
        "primary_key": "product_id",
        "required": ["product_id", "product_name", "category", "subcategory", "unit_cost", "unit_price"],
        "optional": [],
        "text": ["product_id", "product_name", "category", "subcategory"],
        "numeric": ["unit_cost", "unit_price"],
    },
    "orders": {
        "file": "orders.csv",
        "primary_key": "order_id",
        "required": ["order_id", "order_date", "customer_id", "product_id", "quantity", "discount", "payment_method", "order_status"],
        "optional": ["gross_sales", "discount_amount", "net_sales"],
        "text": ["order_id", "customer_id", "product_id", "payment_method", "order_status"],
        "dates": ["order_date"],
        "numeric": ["quantity", "discount"],
    },
}

VALID_CATEGORIES = {
    "customer_region": {"Northeast", "Southeast", "Midwest", "Southwest", "West"},
    "customer_city": {"Sampleton", "Mapleford", "Riverton", "Oakridge", "Pinehaven", "Clearwater", "Lakeview", "Cedarfield", "Fairview", "Redstone", "Sagebrush", "Mesa Vista", "Summit Bay", "Silverpine", "Westhaven"},
    "customer_segment": {"Consumer", "Small Business", "Enterprise"},
    "category": {"Electronics", "Home & Kitchen", "Apparel", "Sports & Outdoors", "Beauty & Personal Care"},
    "subcategory": {"Audio", "Accessories", "Cameras", "Cookware", "Storage", "Lighting", "Outerwear", "Basics", "Activewear", "Fitness", "Camping", "Cycling", "Skincare", "Haircare", "Personal Care"},
    "payment_method": {"Credit Card", "Debit Card", "PayPal", "Gift Card", "Buy Now Pay Later"},
    "order_status": {"Completed", "Shipped", "Processing", "Cancelled", "Returned"},
}


class ValidationInputError(Exception):
    """Raised when a required CSV cannot be loaded for validation."""


def load_datasets(data_dir: Path = DATA_DIR) -> dict[str, pd.DataFrame]:
    """Load all three CSVs, preserving identifiers and values as strings initially."""
    datasets = {}
    for name, schema in SCHEMAS.items():
        path = data_dir / schema["file"]
        if not path.is_file():
            raise ValidationInputError(f"Required dataset not found: {path}")
        try:
            datasets[name] = pd.read_csv(path, dtype="string")
        except (OSError, pd.errors.ParserError, UnicodeDecodeError) as exc:
            raise ValidationInputError(f"Could not read {path}: {exc}") from exc
    return datasets


def _new_report(name: str, frame: pd.DataFrame, schema: dict[str, Any]) -> dict[str, Any]:
    required = set(schema["required"])
    recognized = required | set(schema.get("optional", []))
    actual = set(frame.columns)
    missing_columns = sorted(required - actual)
    unexpected_columns = sorted(actual - recognized)
    missing_values = {}
    for column in frame.columns:
        values = frame[column]
        missing = values.isna()
        if pd.api.types.is_string_dtype(values.dtype) or values.dtype == object:
            missing |= values.map(
                lambda value: isinstance(value, str)
                and value.strip().casefold() in {"", "na", "n/a", "null", "none", "nan"}
            )
        count = int(missing.sum())
        if count:
            missing_values[str(column)] = count
    primary_key = schema["primary_key"]
    duplicate_primary_keys = 0
    if primary_key in frame.columns:
        duplicate_primary_keys = int(frame[primary_key].duplicated(keep=False).sum())

    return {
        "dataset_name": name,
        "row_count": int(len(frame)),
        "column_count": int(len(frame.columns)),
        "missing_columns": missing_columns,
        "unexpected_columns": unexpected_columns,
        "missing_values": missing_values,
        "duplicate_primary_keys": duplicate_primary_keys,
        "invalid_values": {},
        "foreign_key_violations": {},
        "validation_status": "PASS",
    }


def _add_invalid(report: dict[str, Any], field: str, count: int) -> None:
    if count:
        report["invalid_values"][field] = int(count)


def _validate_dataset(
    name: str,
    frame: pd.DataFrame,
    accepted_categories: dict[str, set[str] | list[str]] | None = None,
) -> dict[str, Any]:
    schema = SCHEMAS[name]
    report = _new_report(name, frame, schema)
    available = set(frame.columns)

    for field in schema.get("text", []):
        if field in available:
            _add_invalid(report, f"{field} (not text)", int((frame[field].notna() & ~frame[field].map(lambda value: isinstance(value, str))).sum()))

    for field in schema.get("dates", []):
        if field in available:
            parsed = pd.to_datetime(frame[field], errors="coerce", format="mixed")
            _add_invalid(report, f"{field} (invalid date)", int((frame[field].notna() & parsed.isna()).sum()))

    numeric_values: dict[str, pd.Series] = {}
    for field in schema.get("numeric", []):
        if field in available:
            converted = pd.to_numeric(frame[field], errors="coerce")
            numeric_values[field] = converted
            _add_invalid(report, f"{field} (not numeric)", int((frame[field].notna() & converted.isna()).sum()))

    categories = VALID_CATEGORIES if accepted_categories is None else accepted_categories
    for field, accepted_values in categories.items():
        if field in available:
            invalid = frame[field].notna() & ~frame[field].isin(accepted_values)
            _add_invalid(report, f"{field} (unsupported category)", int(invalid.sum()))

    if name == "products":
        cost = numeric_values.get("unit_cost")
        price = numeric_values.get("unit_price")
        if cost is not None:
            _add_invalid(report, "unit_cost (negative)", int((cost < 0).sum()))
        if price is not None:
            _add_invalid(report, "unit_price (negative)", int((price < 0).sum()))
        if cost is not None and price is not None:
            comparable = cost.notna() & price.notna()
            _add_invalid(report, "unit_price (not greater than unit_cost)", int((comparable & (price <= cost)).sum()))

    if name == "orders":
        quantity = numeric_values.get("quantity")
        discount = numeric_values.get("discount")
        if quantity is not None:
            _add_invalid(report, "quantity (not greater than zero)", int((quantity <= 0).sum()))
        if discount is not None:
            _add_invalid(report, "discount (outside 0 to 1)", int(((discount < 0) | (discount > 1)).sum()))

    if report["missing_columns"] or report["missing_values"] or report["duplicate_primary_keys"] or report["invalid_values"]:
        report["validation_status"] = "FAIL"
    elif report["unexpected_columns"]:
        report["validation_status"] = "WARNING"
    return report


def _check_foreign_keys(
    orders: pd.DataFrame,
    customers: pd.DataFrame,
    products: pd.DataFrame,
    order_report: dict[str, Any],
) -> None:
    """Check order references only when all relevant key columns are available."""
    checks = [
        ("customer_id", customers, "customer_id"),
        ("product_id", products, "product_id"),
    ]
    for order_field, parent, parent_field in checks:
        if order_field not in orders.columns or parent_field not in parent.columns:
            continue
        known_ids = set(parent[parent_field].dropna())
        violations = int((orders[order_field].notna() & ~orders[order_field].isin(known_ids)).sum())
        if violations:
            order_report["foreign_key_violations"][order_field] = violations
            order_report["validation_status"] = "FAIL"


def validate_dataframes(
    datasets: dict[str, pd.DataFrame],
    accepted_categories: dict[str, set[str] | list[str]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Validate loaded dataframes and return a structured report by dataset."""
    reports = {
        name: _validate_dataset(name, datasets[name], accepted_categories)
        for name in SCHEMAS
        if name in datasets
    }
    if set(reports) != set(SCHEMAS):
        absent = sorted(set(SCHEMAS) - set(reports))
        raise ValidationInputError(f"Missing datasets for validation: {', '.join(absent)}")
    _check_foreign_keys(datasets["orders"], datasets["customers"], datasets["products"], reports["orders"])
    return reports


def validate_files(data_dir: Path = DATA_DIR) -> dict[str, dict[str, Any]]:
    """Load configured CSV files and validate them."""
    return validate_dataframes(load_datasets(data_dir))


def _print_summary(reports: dict[str, dict[str, Any]]) -> None:
    print("Data quality validation")
    for report in reports.values():
        print(
            f"{report['validation_status']:7} {report['dataset_name']:<10} "
            f"rows={report['row_count']:,} columns={report['column_count']} "
            f"missing={sum(report['missing_values'].values())} "
            f"duplicate_keys={report['duplicate_primary_keys']} "
            f"invalid={sum(report['invalid_values'].values())} "
            f"foreign_key_violations={sum(report['foreign_key_violations'].values())}"
        )
        if report["missing_columns"]:
            print(f"  Missing columns: {', '.join(report['missing_columns'])}")
        if report["unexpected_columns"]:
            print(f"  Unexpected columns: {', '.join(report['unexpected_columns'])}")
        for field, count in report["invalid_values"].items():
            print(f"  Invalid {field}: {count}")
        for field, count in report["foreign_key_violations"].items():
            print(f"  Foreign-key violations for {field}: {count}")
    overall = "FAIL" if any(r["validation_status"] == "FAIL" for r in reports.values()) else (
        "WARNING" if any(r["validation_status"] == "WARNING" for r in reports.values()) else "PASS"
    )
    print(f"Overall status: {overall}")


def main() -> int:
    try:
        reports = validate_files()
    except ValidationInputError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2

    _print_summary(reports)
    return 1 if any(report["validation_status"] == "FAIL" for report in reports.values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
