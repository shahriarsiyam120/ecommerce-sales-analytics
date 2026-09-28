"""Tests for duplicate handling, missing-value cleaning, and sales arithmetic."""

import unittest

import pandas as pd

from src.cleaning.data_cleaner import add_sales_columns, clean_orders


class DataCleaningTests(unittest.TestCase):
    def test_exact_duplicates_removed_and_null_markers_standardized(self) -> None:
        source = pd.DataFrame({
            "order_id": ["O1", "O1"],
            "order_date": ["2025-01-01", "2025-01-01"],
            "customer_id": ["C1", "C1"],
            "product_id": ["P1", "P1"],
            "quantity": ["2", "2"],
            "discount": ["null", "null"],
            "payment_method": ["Card", "Card"],
            "order_status": ["Completed", "Completed"],
        })
        cleaned, _, removed = clean_orders(source)
        self.assertEqual(removed, 1)
        self.assertEqual(len(cleaned), 1)
        self.assertTrue(pd.isna(cleaned.loc[0, "discount"]))

    def test_gross_discount_and_net_sales_use_quantity_price_and_rate(self) -> None:
        orders = pd.DataFrame({
            "product_id": ["P1"], "quantity": [2], "discount": [0.25]
        })
        products = pd.DataFrame({"product_id": ["P1"], "unit_price": [10.0]})
        result, _ = add_sales_columns(orders, products)
        self.assertEqual(result.loc[0, "gross_sales"], 20.0)
        self.assertEqual(result.loc[0, "discount_amount"], 5.0)
        self.assertEqual(result.loc[0, "net_sales"], 15.0)

    def test_unmatched_product_does_not_invent_revenue(self) -> None:
        orders = pd.DataFrame({
            "product_id": ["UNKNOWN"], "quantity": [2], "discount": [0.0]
        })
        products = pd.DataFrame({"product_id": ["P1"], "unit_price": [10.0]})
        result, _ = add_sales_columns(orders, products)
        self.assertTrue(pd.isna(result.loc[0, "gross_sales"]))
        self.assertTrue(pd.isna(result.loc[0, "net_sales"]))


if __name__ == "__main__":
    unittest.main()