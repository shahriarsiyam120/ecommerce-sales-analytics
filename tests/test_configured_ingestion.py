"""Tests for configured source loading and pre-clean validation."""

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.ingestion.configured_pipeline import (
    IngestionError,
    load_configured_datasets,
    run_configured_pipeline,
)
from src.analytics.advanced_analytics import PROJECT_ROOT


def valid_frames() -> dict[str, pd.DataFrame]:
    return {
        "customers": pd.DataFrame({
            "customer_id": ["C1"], "customer_name": ["Customer"],
            "customer_email": ["customer@example.invalid"], "customer_region": ["Region A"],
            "customer_city": ["City A"], "customer_segment": ["Retail"],
            "signup_date": ["2025-01-01"],
        }),
        "products": pd.DataFrame({
            "product_id": ["P1"], "product_name": ["Product"], "category": ["Goods"],
            "subcategory": ["General"], "unit_cost": [10.0], "unit_price": [20.0],
        }),
        "orders": pd.DataFrame({
            "order_id": ["O1"], "order_date": ["2025-01-02"], "customer_id": ["C1"],
            "product_id": ["P1"], "quantity": [2], "discount": [0.1],
            "payment_method": ["Card"], "order_status": ["Completed"],
        }),
    }


class ConfiguredIngestionTests(unittest.TestCase):
    def test_configured_pipeline_runs_existing_sample_to_temporary_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            configuration = {
                "source_type": "files",
                "datasets": {
                    name: {"path": f"data/sample/{name}.csv"}
                    for name in ("customers", "products", "orders")
                },
                "accepted_categories": {},
                "output_directory": str(Path(temp_dir) / "processed"),
            }
            result = run_configured_pipeline(configuration, project_root=PROJECT_ROOT)
            self.assertEqual(result["raw_validation"]["orders"]["validation_status"], "PASS")
            self.assertEqual(result["processed_validation"]["orders"]["validation_status"], "PASS")
            self.assertEqual(result["analytics"]["kpis"].iloc[0]["total_orders"], 5000)
            self.assertTrue(
                (Path(temp_dir) / "processed" / "analytics" / "orders_enriched.csv").is_file()
            )
            self.assertTrue(
                (Path(temp_dir) / "processed" / "cleaning_report.json").is_file()
            )

    def test_csv_column_mapping_standardizes_source_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            frames = valid_frames()
            entries = {}
            for name, frame in frames.items():
                renamed = frame.rename(columns={frame.columns[0]: "Source Key"})
                path = root / f"{name}.csv"
                renamed.to_csv(path, index=False)
                entries[name] = {
                    "path": path.name,
                    "column_mapping": {"Source Key": frame.columns[0]},
                }

            loaded = load_configured_datasets(
                {"source_type": "files", "datasets": entries}, project_root=root
            )
            self.assertIn("customer_id", loaded["customers"])
            self.assertEqual(loaded["orders"].loc[0, "order_id"], "O1")

    def test_excel_and_parquet_sources_are_read(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            frames = valid_frames()
            formats = {"customers": "csv", "products": "excel", "orders": "parquet"}
            entries = {}
            extensions = {"csv": ".csv", "excel": ".xlsx", "parquet": ".parquet"}
            for name, frame in frames.items():
                file_format = formats[name]
                path = root / f"{name}{extensions[file_format]}"
                if file_format == "csv":
                    frame.to_csv(path, index=False)
                elif file_format == "excel":
                    frame.to_excel(path, index=False)
                else:
                    frame.to_parquet(path, index=False)
                entries[name] = {"path": path.name, "format": file_format}

            loaded = load_configured_datasets(
                {"source_type": "files", "datasets": entries}, project_root=root
            )
            self.assertEqual(loaded["products"].loc[0, "product_id"], "P1")
            self.assertEqual(loaded["orders"].loc[0, "order_id"], "O1")

    def test_missing_required_fields_stop_before_cleaning(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            frames = valid_frames()
            frames["customers"] = frames["customers"].drop(columns="customer_email")
            entries = {}
            for name, frame in frames.items():
                path = root / f"{name}.csv"
                frame.to_csv(path, index=False)
                entries[name] = {"path": path.name}

            with self.assertRaisesRegex(
                IngestionError, r"before cleaning:[\s\S]*customer_email"
            ):
                run_configured_pipeline(
                    {
                        "source_type": "files",
                        "datasets": entries,
                        "output_directory": "processed",
                        "accepted_categories": {},
                    },
                    project_root=root,
                )
            self.assertFalse((root / "processed").exists())

    def test_column_mapping_rejects_duplicate_destinations(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = root / "source.csv"
            pd.DataFrame(columns=["old", "other"]).to_csv(path, index=False)
            configuration = {
                "source_type": "files",
                "datasets": {
                    name: {
                        "path": path.name,
                        "column_mapping": {"old": "same", "other": "same"},
                    }
                    for name in ("customers", "products", "orders")
                }
            }
            with self.assertRaisesRegex(IngestionError, "duplicate internal column"):
                load_configured_datasets(configuration, project_root=root)


if __name__ == "__main__":
    unittest.main()