"""Edge-case tests for input schemas, values, and relationships."""

import unittest

import pandas as pd

from src.validation.data_validator import validate_dataframes
from tests.test_configured_ingestion import valid_frames


def validator_frames() -> dict[str, pd.DataFrame]:
    frames = valid_frames()
    frames["customers"]["customer_email"] = "customer@example.invalid"
    frames["customers"]["customer_city"] = "City A"
    return frames


class DataValidationTests(unittest.TestCase):
    def test_missing_column_and_blank_value_are_reported(self) -> None:
        datasets = validator_frames()
        datasets["customers"] = datasets["customers"].drop(columns="customer_email")
        report = validate_dataframes(datasets, accepted_categories={})
        self.assertIn("customer_email", report["customers"]["missing_columns"])

        datasets = validator_frames()
        datasets["customers"].loc[0, "customer_name"] = "  "
        report = validate_dataframes(datasets, accepted_categories={})
        self.assertEqual(report["customers"]["missing_values"]["customer_name"], 1)

    def test_duplicate_primary_key_and_foreign_key_are_reported(self) -> None:
        datasets = validator_frames()
        datasets["customers"] = pd.concat(
            [datasets["customers"], datasets["customers"]], ignore_index=True
        )
        datasets["orders"].loc[0, "customer_id"] = "UNKNOWN"
        report = validate_dataframes(datasets, accepted_categories={})
        self.assertEqual(report["customers"]["duplicate_primary_keys"], 2)
        self.assertEqual(report["orders"]["foreign_key_violations"]["customer_id"], 1)

    def test_configured_category_values_replace_sample_whitelist(self) -> None:
        datasets = validator_frames()
        datasets["customers"].loc[0, "customer_region"] = "Region A"
        report = validate_dataframes(
            datasets, accepted_categories={"customer_region": ["Region A"]}
        )
        self.assertEqual(report["customers"]["validation_status"], "PASS")


if __name__ == "__main__":
    unittest.main()