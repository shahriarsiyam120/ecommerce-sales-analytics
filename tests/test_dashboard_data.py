"""Tests for dashboard data loading and filter-aware calculations."""

import unittest
from datetime import date

import pandas as pd

from dashboard.data_access import (
    calculate_kpis,
    customer_performance,
    customer_revenue_distribution,
    discount_performance,
    filter_orders,
    monthly_performance,
    product_performance,
)
from tests.test_advanced_analytics import sample_datasets
from src.analytics.advanced_analytics import build_advanced_analytics


class DashboardDataTests(unittest.TestCase):
    def setUp(self) -> None:
        tables = build_advanced_analytics(sample_datasets())
        self.orders = tables["orders_enriched"]
        self.products = tables["products"]

    def test_filters_apply_dates_and_dimensions(self) -> None:
        selected = filter_orders(
            self.orders,
            start_date=date(2025, 1, 16),
            regions=["West"],
            categories=["Outdoor"],
        )
        self.assertEqual(selected["order_id"].tolist(), ["O2"])

    def test_empty_selection_returns_zero_metrics(self) -> None:
        selected = filter_orders(self.orders, regions=[])
        kpis = calculate_kpis(selected, self.products)
        self.assertEqual(kpis["total_revenue"], 0)
        self.assertEqual(kpis["total_orders"], 0)
        self.assertEqual(kpis["total_customers"], 0)

    def test_monthly_trend_and_zero_sales_catalog_items(self) -> None:
        monthly = monthly_performance(self.orders)
        self.assertEqual(monthly["orders"].tolist(), [2, 1])
        self.assertEqual(monthly["net_sales"].tolist(), [140.0, 120.0])
        products = product_performance(self.orders.iloc[0:0], self.products)
        self.assertEqual(len(products), 2)
        self.assertTrue((products["net_sales"] == 0).all())

    def test_product_totals_follow_filtered_orders(self) -> None:
        products = product_performance(self.orders.iloc[[0]], self.products)
        product_one = products.set_index("product_id").loc["P1"]
        self.assertEqual(product_one["product_total_quantity"], 2)
        self.assertEqual(product_one["product_total_revenue"], 90.0)

    def test_discount_comparison_is_available_for_selected_orders(self) -> None:
        discount = discount_performance(self.orders)
        self.assertEqual(discount["orders"].sum(), 3)
        self.assertEqual(discount["net_sales"].sum(), 260.0)

    def test_customer_summary_uses_non_personal_identifiers(self) -> None:
        customers = customer_performance(self.orders)
        self.assertIn("customer_id", customers)
        self.assertNotIn("customer_email", customers)
        self.assertEqual(customers["orders"].sum(), 3)
        distribution = customer_revenue_distribution(self.orders)
        self.assertEqual(distribution["customers"].sum(), 2)


if __name__ == "__main__":
    unittest.main()