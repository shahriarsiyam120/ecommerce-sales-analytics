"""Focused tests for advanced analytics calculations."""

import unittest

import pandas as pd

from src.analytics.advanced_analytics import (
    AnalyticsInputError,
    build_advanced_analytics,
)


def sample_datasets() -> dict[str, pd.DataFrame]:
    return {
        "customers": pd.DataFrame({
            "customer_id": ["C1", "C2", "C3"],
            "customer_region": ["West", "East", "West"],
            "customer_segment": ["Consumer", "Enterprise", "Consumer"],
        }),
        "products": pd.DataFrame({
            "product_id": ["P1", "P2"],
            "product_name": ["One", "Two"],
            "category": ["Home", "Outdoor"],
            "subcategory": ["Cookware", "Camping"],
        }),
        "orders": pd.DataFrame({
            "order_id": ["O1", "O2", "O3"],
            "order_date": ["2025-01-15", "2025-01-20", "2025-02-01"],
            "customer_id": ["C1", "C1", "C2"],
            "product_id": ["P1", "P2", "P1"],
            "quantity": [2, 1, 3],
            "discount": [0.1, 0.0, 0.2],
            "gross_sales": [100.0, 50.0, 150.0],
            "discount_amount": [10.0, 0.0, 30.0],
            "net_sales": [90.0, 50.0, 120.0],
            "payment_method": ["Card", "Cash", "Card"],
            "order_status": ["Completed", "Returned", "Completed"],
        }),
    }


class AdvancedAnalyticsTests(unittest.TestCase):
    def test_customer_and_product_features_reconcile_to_orders(self) -> None:
        result = build_advanced_analytics(sample_datasets())
        customer_one = result["customers"].set_index("customer_id").loc["C1"]
        product_one = result["products"].set_index("product_id").loc["P1"]

        self.assertEqual(customer_one["customer_order_count"], 2)
        self.assertEqual(customer_one["customer_total_revenue"], 140.0)
        self.assertEqual(customer_one["customer_average_order_value"], 70.0)
        segments = result["customers"].set_index("customer_id")["value_segment"]
        self.assertEqual(segments["C3"], "Low Value")
        self.assertEqual(segments["C1"], "High Value")
        self.assertEqual(segments["C2"], "Medium Value")
        self.assertEqual(product_one["quantity_sold"], 5)
        self.assertEqual(product_one["net_sales"], 210.0)
        self.assertEqual(product_one["product_total_quantity"], 5)
        self.assertEqual(product_one["product_total_revenue"], 210.0)
        self.assertEqual(result["kpis"].iloc[0]["total_revenue"], 260.0)
        self.assertEqual(result["kpis"].iloc[0]["average_order_value"], 260 / 3)

    def test_month_growth_and_revenue_contribution(self) -> None:
        result = build_advanced_analytics(sample_datasets())
        monthly = result["monthly"].set_index("month_start")

        self.assertEqual(monthly.loc[pd.Timestamp("2025-01-01"), "net_sales"], 140.0)
        self.assertAlmostEqual(
            monthly.loc[pd.Timestamp("2025-02-01"), "monthly_revenue_growth"],
            -20 / 140,
        )
        self.assertAlmostEqual(result["categories"]["revenue_contribution"].sum(), 1.0)

    def test_zero_sales_products_and_duplicate_dimension_keys(self) -> None:
        datasets = sample_datasets()
        result = build_advanced_analytics(datasets)
        product_two = result["products"].set_index("product_id").loc["P2"]
        self.assertEqual(product_two["quantity_sold"], 1)

        datasets["customers"] = pd.concat(
            [datasets["customers"], datasets["customers"].iloc[[0]]], ignore_index=True
        )
        with self.assertRaisesRegex(AnalyticsInputError, "duplicate customer_id"):
            build_advanced_analytics(datasets)

    def test_empty_order_tables_produce_zero_kpis(self) -> None:
        datasets = sample_datasets()
        datasets["orders"] = datasets["orders"].iloc[0:0]
        result = build_advanced_analytics(datasets)
        self.assertEqual(result["kpis"].iloc[0]["total_orders"], 0)
        self.assertEqual(result["kpis"].iloc[0]["total_revenue"], 0)


if __name__ == "__main__":
    unittest.main()