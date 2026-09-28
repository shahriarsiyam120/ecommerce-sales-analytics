"""Generate reproducible, entirely synthetic e-commerce CSV data."""

from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path


SEED = 20260928
CUSTOMER_COUNT = 500
PRODUCT_COUNT = 100
ORDER_COUNT = 5_000
DATE_START = date(2025, 1, 1)
DATE_END = date(2025, 12, 31)
OUTPUT_DIR = Path(__file__).resolve().parents[2] / "data" / "sample"

CUSTOMER_FIELDS = [
    "customer_id", "customer_name", "customer_email", "customer_region",
    "customer_city", "customer_segment", "signup_date",
]
PRODUCT_FIELDS = [
    "product_id", "product_name", "category", "subcategory", "unit_cost",
    "unit_price",
]
ORDER_FIELDS = [
    "order_id", "order_date", "customer_id", "product_id", "quantity",
    "discount", "payment_method", "order_status",
]

REGIONS = {
    "Northeast": ["Sampleton", "Mapleford", "Riverton"],
    "Southeast": ["Oakridge", "Pinehaven", "Clearwater"],
    "Midwest": ["Lakeview", "Cedarfield", "Fairview"],
    "Southwest": ["Redstone", "Sagebrush", "Mesa Vista"],
    "West": ["Summit Bay", "Silverpine", "Westhaven"],
}
SEGMENTS = ["Consumer", "Small Business", "Enterprise"]
CATEGORY_PRODUCTS = {
    "Electronics": {
        "Audio": ["Wireless Headphones", "Bluetooth Speaker", "Studio Earbuds"],
        "Accessories": ["USB-C Hub", "Charging Cable", "Laptop Stand"],
        "Cameras": ["Action Camera", "Webcam", "Tripod Kit"],
    },
    "Home & Kitchen": {
        "Cookware": ["Saucepan Set", "Chef Knife", "Baking Tray"],
        "Storage": ["Glass Container Set", "Shelf Organizer", "Storage Basket"],
        "Lighting": ["Desk Lamp", "Floor Lamp", "LED Light Strip"],
    },
    "Apparel": {
        "Outerwear": ["Rain Jacket", "Fleece Pullover", "Puffer Vest"],
        "Basics": ["Cotton T-Shirt", "Crew Socks", "Everyday Hoodie"],
        "Activewear": ["Running Shorts", "Training Leggings", "Sports Top"],
    },
    "Sports & Outdoors": {
        "Fitness": ["Yoga Mat", "Resistance Band Set", "Kettlebell"],
        "Camping": ["Camping Lantern", "Travel Hammock", "Sleeping Bag"],
        "Cycling": ["Bike Helmet", "Repair Kit", "Water Bottle Cage"],
    },
    "Beauty & Personal Care": {
        "Skincare": ["Daily Moisturizer", "Gentle Cleanser", "Face Serum"],
        "Haircare": ["Shampoo Set", "Hair Brush", "Travel Dryer"],
        "Personal Care": ["Grooming Kit", "Electric Toothbrush", "Travel Mirror"],
    },
}
PRICE_RANGES = {
    "Electronics": (12, 180),
    "Home & Kitchen": (8, 120),
    "Apparel": (10, 95),
    "Sports & Outdoors": (9, 150),
    "Beauty & Personal Care": (6, 85),
}
PAYMENT_METHODS = ["Credit Card", "Debit Card", "PayPal", "Gift Card", "Buy Now Pay Later"]
ORDER_STATUSES = ["Completed", "Shipped", "Processing", "Cancelled", "Returned"]


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _build_customers(rng: random.Random) -> list[dict[str, object]]:
    given_names = ["Alex", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Avery", "Quinn", "Jamie", "Cameron"]
    family_names = ["Sample", "Example", "Demo", "Testwell", "Fiction", "Mockley", "Placeholder", "Synthetic", "Practice", "Dataset"]
    rows = []
    for number in range(1, CUSTOMER_COUNT + 1):
        region = rng.choice(list(REGIONS))
        signup = DATE_START - timedelta(days=rng.randint(0, 730))
        rows.append({
            "customer_id": f"C{number:05d}",
            "customer_name": f"{rng.choice(given_names)} {rng.choice(family_names)}",
            "customer_email": f"customer{number:05d}@example.invalid",
            "customer_region": region,
            "customer_city": rng.choice(REGIONS[region]),
            "customer_segment": rng.choices(SEGMENTS, weights=[70, 24, 6], k=1)[0],
            "signup_date": signup.isoformat(),
        })
    return rows


def _build_products(rng: random.Random) -> list[dict[str, object]]:
    choices = [
        (category, subcategory, name)
        for category, subcategories in CATEGORY_PRODUCTS.items()
        for subcategory, names in subcategories.items()
        for name in names
    ]
    rows = []
    for number in range(1, PRODUCT_COUNT + 1):
        category, subcategory, base_name = rng.choice(choices)
        low, high = PRICE_RANGES[category]
        price = round(rng.uniform(low, high), 2)
        cost = round(price * rng.uniform(0.38, 0.72), 2)
        rows.append({
            "product_id": f"P{number:04d}",
            "product_name": f"{base_name} Model {number:03d}",
            "category": category,
            "subcategory": subcategory,
            "unit_cost": f"{cost:.2f}",
            "unit_price": f"{price:.2f}",
        })
    return rows


def _build_orders(rng: random.Random, customers: list[dict[str, object]], products: list[dict[str, object]]) -> list[dict[str, object]]:
    span = (DATE_END - DATE_START).days
    rows = []
    for number in range(1, ORDER_COUNT + 1):
        order_date = DATE_START + timedelta(days=rng.randint(0, span))
        rows.append({
            "order_id": f"O{number:06d}",
            "order_date": order_date.isoformat(),
            "customer_id": rng.choice(customers)["customer_id"],
            "product_id": rng.choice(products)["product_id"],
            "quantity": rng.choices([1, 2, 3, 4, 5, 6], weights=[52, 25, 12, 6, 3, 2], k=1)[0],
            "discount": f"{rng.choices([0, 0.05, 0.10, 0.15, 0.20], weights=[55, 15, 16, 10, 4], k=1)[0]:.2f}",
            "payment_method": rng.choice(PAYMENT_METHODS),
            "order_status": rng.choices(ORDER_STATUSES, weights=[70, 12, 8, 6, 4], k=1)[0],
        })
    return rows


def validate_data(customers: list[dict[str, object]], products: list[dict[str, object]], orders: list[dict[str, object]]) -> list[str]:
    """Return validation errors; an empty result means the generated data passed."""
    errors = []
    datasets = [
        ("customers", customers, CUSTOMER_COUNT, "customer_id"),
        ("products", products, PRODUCT_COUNT, "product_id"),
        ("orders", orders, ORDER_COUNT, "order_id"),
    ]
    for name, rows, expected_count, id_field in datasets:
        if len(rows) != expected_count:
            errors.append(f"{name}: expected {expected_count} rows, got {len(rows)}")
        ids = [row[id_field] for row in rows]
        if len(ids) != len(set(ids)):
            errors.append(f"{name}: duplicate {id_field} values")
        if any(value is None or value == "" for row in rows for value in row.values()):
            errors.append(f"{name}: missing values found")

    customer_ids = {row["customer_id"] for row in customers}
    product_ids = {row["product_id"] for row in products}
    if any(row["customer_id"] not in customer_ids for row in orders):
        errors.append("orders: customer_id foreign-key integrity failed")
    if any(row["product_id"] not in product_ids for row in orders):
        errors.append("orders: product_id foreign-key integrity failed")

    dates = [date.fromisoformat(str(row["order_date"])) for row in orders]
    if not dates or min(dates) < DATE_START or max(dates) > DATE_END:
        errors.append(f"orders: dates fall outside {DATE_START} to {DATE_END}")
    return errors


def main() -> None:
    rng = random.Random(SEED)
    customers = _build_customers(rng)
    products = _build_products(rng)
    orders = _build_orders(rng, customers, products)
    errors = validate_data(customers, products, orders)
    if errors:
        raise ValueError("Generated data failed validation: " + "; ".join(errors))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _write_csv(OUTPUT_DIR / "customers.csv", CUSTOMER_FIELDS, customers)
    _write_csv(OUTPUT_DIR / "products.csv", PRODUCT_FIELDS, products)
    _write_csv(OUTPUT_DIR / "orders.csv", ORDER_FIELDS, orders)

    actual_dates = [date.fromisoformat(str(row["order_date"])) for row in orders]
    print("Sample data generated and validated successfully")
    print(f"  Customers: {len(customers):,} rows; unique IDs; no missing values")
    print(f"  Products:  {len(products):,} rows; unique IDs; no missing values")
    print(f"  Orders:    {len(orders):,} rows; unique IDs; no missing values")
    print("  Foreign keys: all order customer and product IDs exist")
    print(f"  Order date range: {min(actual_dates)} to {max(actual_dates)}")
    print(f"  Output: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
