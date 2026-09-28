"""Reusable descriptive analytics built from standardized cleaned tables."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
ANALYTICS_DIR = PROCESSED_DIR / "analytics"
INPUT_FILES = {
    "customers": "customers_cleaned.csv",
    "products": "products_cleaned.csv",
    "orders": "orders_cleaned.csv",
}
REQUIRED_COLUMNS = {
    "customers": {"customer_id", "customer_region"},
    "products": {"product_id", "product_name", "category", "subcategory"},
    "orders": {
        "order_id", "order_date", "customer_id", "product_id", "quantity",
        "discount", "gross_sales", "discount_amount", "net_sales",
        "payment_method", "order_status",
    },
}


class AnalyticsInputError(ValueError):
    """Raised when cleaned data does not meet the analytics input contract."""


def load_cleaned_data(data_dir: Path = PROCESSED_DIR) -> dict[str, pd.DataFrame]:
    """Load cleaned tables using project-relative defaults."""
    datasets: dict[str, pd.DataFrame] = {}
    for name, filename in INPUT_FILES.items():
        path = data_dir / filename
        if not path.is_file():
            raise FileNotFoundError(f"Required cleaned dataset not found: {path}")
        datasets[name] = pd.read_csv(path)
    return datasets


def _validate_contract(datasets: dict[str, pd.DataFrame]) -> None:
    missing_tables = sorted(set(REQUIRED_COLUMNS) - set(datasets))
    if missing_tables:
        raise AnalyticsInputError(f"Missing cleaned datasets: {', '.join(missing_tables)}")
    for name, required in REQUIRED_COLUMNS.items():
        missing = sorted(required - set(datasets[name].columns))
        if missing:
            raise AnalyticsInputError(
                f"{name} is missing required analytics columns: {', '.join(missing)}"
            )


def _numeric(frame: pd.DataFrame, columns: list[str]) -> None:
    for column in columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")


def _with_contribution(frame: pd.DataFrame, revenue_column: str = "net_sales") -> pd.DataFrame:
    result = frame.sort_values(revenue_column, ascending=False).reset_index(drop=True)
    total_revenue = result[revenue_column].sum()
    result["revenue_contribution"] = (
        result[revenue_column] / total_revenue if total_revenue else 0.0
    )
    result["cumulative_revenue_contribution"] = result["revenue_contribution"].cumsum()
    result["within_top_80_percent"] = (
        result["cumulative_revenue_contribution"] - result["revenue_contribution"] < 0.8
    )
    return result


def build_advanced_analytics(datasets: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Create order features and business summaries from cleaned input frames.

    Revenue uses net sales across all recorded order statuses. Customer value is
    descriptive over the observed data window, not a prediction of future value.
    """
    _validate_contract(datasets)
    customers = datasets["customers"].copy()
    products = datasets["products"].copy()
    orders = datasets["orders"].copy()
    _numeric(orders, ["quantity", "discount", "gross_sales", "discount_amount", "net_sales"])
    orders["order_date"] = pd.to_datetime(orders["order_date"], errors="coerce")
    if customers["customer_id"].duplicated().any():
        raise AnalyticsInputError("customers contains duplicate customer_id values")
    if products["product_id"].duplicated().any():
        raise AnalyticsInputError("products contains duplicate product_id values")

    orders["order_value"] = orders["net_sales"]
    orders["discount_rate"] = orders["discount_amount"].div(
        orders["gross_sales"].where(orders["gross_sales"] != 0)
    ).fillna(0.0)
    orders["month"] = orders["order_date"].dt.month.astype("Int64")
    orders["quarter"] = orders["order_date"].dt.quarter.astype("Int64")
    orders["year"] = orders["order_date"].dt.year.astype("Int64")
    orders["month_start"] = orders["order_date"].dt.to_period("M").dt.to_timestamp()

    enriched = orders.merge(products, on="product_id", how="left", validate="many_to_one")
    customer_fields = ["customer_id", "customer_region"]
    if "customer_segment" in customers:
        customer_fields.append("customer_segment")
    enriched = enriched.merge(
        customers[customer_fields], on="customer_id", how="left", validate="many_to_one"
    )

    customer_orders = orders.groupby("customer_id", dropna=False).agg(
        customer_order_count=("order_id", "nunique"),
        customer_total_revenue=("net_sales", "sum"),
    )
    customer_orders["customer_average_order_value"] = customer_orders[
        "customer_total_revenue"
    ].div(customer_orders["customer_order_count"].replace(0, pd.NA))
    customer_analysis = customers.merge(
        customer_orders, left_on="customer_id", right_index=True, how="left"
    )
    customer_analysis[["customer_order_count", "customer_total_revenue"]] = customer_analysis[
        ["customer_order_count", "customer_total_revenue"]
    ].fillna(0)
    customer_analysis["customer_average_order_value"] = customer_analysis[
        "customer_average_order_value"
    ].fillna(0)
    customer_analysis["customer_value_rank"] = customer_analysis[
        "customer_total_revenue"
    ].rank(method="average", pct=True)
    customer_analysis["value_segment"] = "Medium Value"
    customer_analysis.loc[
        customer_analysis["customer_total_revenue"] <= 0, "value_segment"
    ] = "Low Value"
    customer_analysis.loc[
        (customer_analysis["customer_total_revenue"] > 0)
        & (customer_analysis["customer_value_rank"] <= 0.2),
        "value_segment",
    ] = "Low Value"
    customer_analysis.loc[
        (customer_analysis["customer_total_revenue"] > 0)
        & (customer_analysis["customer_value_rank"] >= 0.8),
        "value_segment",
    ] = "High Value"
    if customer_analysis.empty:
        customer_analysis["value_segment"] = pd.Series(dtype="string")

    enriched = enriched.merge(
        customer_analysis[[
            "customer_id", "customer_order_count", "customer_total_revenue",
            "customer_average_order_value", "value_segment",
        ]],
        on="customer_id",
        how="left",
        validate="many_to_one",
    )

    product_totals = enriched.groupby("product_id", dropna=False).agg(
        product_total_quantity=("quantity", "sum"),
        product_total_revenue=("net_sales", "sum"),
        orders=("order_id", "nunique"),
    )
    product_analysis = products.merge(
        product_totals, left_on="product_id", right_index=True, how="left"
    )
    product_columns = ["product_total_quantity", "product_total_revenue", "orders"]
    product_analysis[product_columns] = product_analysis[product_columns].fillna(0)
    product_analysis["quantity_sold"] = product_analysis["product_total_quantity"]
    product_analysis["net_sales"] = product_analysis["product_total_revenue"]
    product_analysis = _with_contribution(product_analysis)

    def summarize(field: str) -> pd.DataFrame:
        summary = enriched.groupby(field, dropna=False).agg(
            orders=("order_id", "nunique"),
            quantity_sold=("quantity", "sum"),
            gross_sales=("gross_sales", "sum"),
            discount_amount=("discount_amount", "sum"),
            net_sales=("net_sales", "sum"),
            average_discount_rate=("discount_rate", "mean"),
        ).reset_index()
        summary["average_order_value"] = summary["net_sales"].div(
            summary["orders"].replace(0, pd.NA)
        )
        return _with_contribution(summary)

    category_analysis = summarize("category")
    subcategory_analysis = summarize("subcategory")
    regional_analysis = summarize("customer_region")
    payment_analysis = summarize("payment_method")
    status_analysis = summarize("order_status")

    monthly = enriched.dropna(subset=["month_start"]).groupby("month_start").agg(
        orders=("order_id", "nunique"),
        quantity_sold=("quantity", "sum"),
        gross_sales=("gross_sales", "sum"),
        discount_amount=("discount_amount", "sum"),
        net_sales=("net_sales", "sum"),
        average_discount_rate=("discount_rate", "mean"),
    ).reset_index().sort_values("month_start")
    monthly["average_order_value"] = monthly["net_sales"].div(
        monthly["orders"].replace(0, pd.NA)
    )
    prior_revenue = monthly["net_sales"].shift(1)
    monthly["monthly_revenue_growth"] = (
        (monthly["net_sales"] - prior_revenue) / prior_revenue.where(prior_revenue != 0)
    )
    prior_orders = monthly["orders"].shift(1)
    monthly["monthly_order_growth"] = (
        (monthly["orders"] - prior_orders) / prior_orders.where(prior_orders != 0)
    )
    monthly["revenue_contribution"] = (
        monthly["net_sales"].div(monthly["net_sales"].sum())
        if monthly["net_sales"].sum()
        else 0.0
    )

    discount_bands = pd.cut(
        enriched["discount_rate"].clip(lower=0, upper=1),
        bins=[-0.000001, 0, 0.05, 0.10, 0.20, 1.0],
        labels=["0%", ">0-5%", ">5-10%", ">10-20%", ">20%"],
        include_lowest=True,
    )
    discount_analysis = enriched.assign(discount_band=discount_bands).groupby(
        "discount_band", observed=True, dropna=False
    ).agg(
        order_lines=("order_id", "size"),
        orders=("order_id", "nunique"),
        average_order_value=("order_value", "mean"),
        gross_sales=("gross_sales", "sum"),
        discount_amount=("discount_amount", "sum"),
        net_sales=("net_sales", "sum"),
    ).reset_index()

    segment_analysis = customer_analysis.groupby("value_segment", dropna=False).agg(
        customers=("customer_id", "nunique"),
        orders=("customer_order_count", "sum"),
        customer_total_revenue=("customer_total_revenue", "sum"),
        average_customer_revenue=("customer_total_revenue", "mean"),
        average_order_value=("customer_average_order_value", "mean"),
    ).reset_index()

    total_orders = orders["order_id"].nunique()
    kpis = pd.DataFrame([{
        "total_revenue": float(orders["net_sales"].sum()),
        "total_orders": int(total_orders),
        "total_customers": int(customers["customer_id"].nunique()),
        "total_products": int(products["product_id"].nunique()),
        "total_quantity": float(orders["quantity"].sum()),
        "total_gross_sales": float(orders["gross_sales"].sum()),
        "total_discount_amount": float(orders["discount_amount"].sum()),
        "average_order_value": (
            float(orders["net_sales"].sum() / total_orders) if total_orders else 0.0
        ),
    }])

    return {
        "kpis": kpis,
        "orders_enriched": enriched,
        "customers": customer_analysis.sort_values("customer_total_revenue", ascending=False),
        "customer_segments": segment_analysis,
        "products": product_analysis,
        "categories": category_analysis,
        "subcategories": subcategory_analysis,
        "monthly": monthly,
        "regions": regional_analysis,
        "payment_methods": payment_analysis,
        "order_statuses": status_analysis,
        "discount_impact": discount_analysis,
    }


def save_advanced_analytics(
    tables: dict[str, pd.DataFrame], output_dir: Path = ANALYTICS_DIR
) -> None:
    """Persist reusable analysis tables without modifying cleaned inputs."""
    output_dir.mkdir(parents=True, exist_ok=True)
    filenames = {
        "kpis": "advanced_kpis.csv",
        "orders_enriched": "orders_enriched.csv",
        "customers": "advanced_customer_analysis.csv",
        "customer_segments": "advanced_customer_segments.csv",
        "products": "advanced_product_analysis.csv",
        "categories": "advanced_category_analysis.csv",
        "subcategories": "advanced_subcategory_analysis.csv",
        "monthly": "advanced_monthly_analysis.csv",
        "regions": "advanced_region_analysis.csv",
        "payment_methods": "advanced_payment_method_analysis.csv",
        "order_statuses": "advanced_order_status_analysis.csv",
        "discount_impact": "advanced_discount_analysis.csv",
    }
    for name, filename in filenames.items():
        tables[name].to_csv(output_dir / filename, index=False, date_format="%Y-%m-%d")


def run_advanced_analytics(
    data_dir: Path = PROCESSED_DIR, output_dir: Path = ANALYTICS_DIR
) -> dict[str, pd.DataFrame]:
    """Load cleaned data, calculate advanced summaries, and save the outputs."""
    tables = build_advanced_analytics(load_cleaned_data(data_dir))
    save_advanced_analytics(tables, output_dir)
    return tables


def main() -> int:
    tables = run_advanced_analytics()
    print(f"Advanced analytics generated in {ANALYTICS_DIR}")
    print(f"Orders: {int(tables['kpis'].iloc[0]['total_orders']):,}")
    print(f"Revenue: {tables['kpis'].iloc[0]['total_revenue']:,.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())