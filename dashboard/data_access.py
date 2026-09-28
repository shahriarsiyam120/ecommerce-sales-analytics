"""Data loading and filter-aware summaries for the Streamlit dashboard."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ANALYTICS_DIR = PROJECT_ROOT / "data" / "processed" / "analytics"
INPUT_FILES = {
    "orders": "orders_enriched.csv",
    "products": "advanced_product_analysis.csv",
}
REQUIRED_ORDER_COLUMNS = {
    "order_id", "order_date", "customer_id", "product_id", "category",
    "customer_region", "value_segment", "payment_method", "order_status",
    "quantity", "gross_sales", "discount_amount", "net_sales", "order_value",
}


class DashboardDataError(ValueError):
    """Raised when persisted analytics files are unavailable or incompatible."""


def load_dashboard_data(analytics_dir: Path = ANALYTICS_DIR) -> dict[str, pd.DataFrame]:
    """Read the advanced analytics outputs; this function does not run the pipeline."""
    datasets: dict[str, pd.DataFrame] = {}
    for name, filename in INPUT_FILES.items():
        path = analytics_dir / filename
        if not path.is_file():
            raise FileNotFoundError(
                f"Dashboard data is missing: {path}. Run "
                "`python -m src.analytics.advanced_analytics` from the repository root."
            )
        datasets[name] = pd.read_csv(path)

    missing = sorted(REQUIRED_ORDER_COLUMNS - set(datasets["orders"].columns))
    if missing:
        raise DashboardDataError(
            f"orders_enriched.csv is missing required dashboard columns: {', '.join(missing)}"
        )
    datasets["orders"]["order_date"] = pd.to_datetime(
        datasets["orders"]["order_date"], errors="coerce"
    )
    for column in ["quantity", "gross_sales", "discount_amount", "net_sales", "order_value"]:
        datasets["orders"][column] = pd.to_numeric(
            datasets["orders"][column], errors="coerce"
        )
    return datasets


def get_filter_options(orders: pd.DataFrame) -> dict[str, list[str]]:
    """Return sorted, nonempty choices for all categorical sidebar filters."""
    fields = {
        "regions": "customer_region",
        "customer_segments": "value_segment",
        "categories": "category",
        "order_statuses": "order_status",
        "payment_methods": "payment_method",
    }
    return {
        option: sorted(orders[field].dropna().astype(str).unique().tolist())
        for option, field in fields.items()
        if field in orders.columns
    }


def get_date_bounds(orders: pd.DataFrame) -> tuple[date, date] | None:
    """Return the available calendar range, or None when there are no valid dates."""
    dates = pd.to_datetime(orders["order_date"], errors="coerce").dropna()
    if dates.empty:
        return None
    return dates.min().date(), dates.max().date()


def filter_orders(
    orders: pd.DataFrame,
    start_date: date | None = None,
    end_date: date | None = None,
    regions: list[str] | None = None,
    customer_segments: list[str] | None = None,
    categories: list[str] | None = None,
    order_statuses: list[str] | None = None,
    payment_methods: list[str] | None = None,
) -> pd.DataFrame:
    """Apply dashboard selections to the persisted order-level analytics table."""
    result = orders.copy()
    filters = {
        "customer_region": regions,
        "value_segment": customer_segments,
        "category": categories,
        "order_status": order_statuses,
        "payment_method": payment_methods,
    }
    for field, selected in filters.items():
        if selected is not None:
            if not selected:
                return result.iloc[0:0].copy()
            result = result[result[field].isin(selected)]

    dates = pd.to_datetime(result["order_date"], errors="coerce")
    if start_date is not None:
        result = result[dates >= pd.Timestamp(start_date)]
        dates = dates.loc[result.index]
    if end_date is not None:
        result = result[dates < pd.Timestamp(end_date) + pd.Timedelta(days=1)]
    return result.copy()


def calculate_kpis(
    orders: pd.DataFrame, products: pd.DataFrame
) -> dict[str, int | float]:
    """Calculate selected-transaction metrics and the filtered catalog size."""
    order_count = int(orders["order_id"].nunique()) if not orders.empty else 0
    revenue = float(orders["net_sales"].sum()) if not orders.empty else 0.0
    quantity = float(orders["quantity"].sum()) if not orders.empty else 0.0
    return {
        "total_revenue": revenue,
        "total_orders": order_count,
        "total_customers": int(orders["customer_id"].nunique()) if not orders.empty else 0,
        "total_products": int(products["product_id"].nunique()),
        "total_quantity": quantity,
        "average_order_value": revenue / order_count if order_count else 0.0,
    }


def monthly_performance(orders: pd.DataFrame) -> pd.DataFrame:
    """Aggregate revenue and order count by calendar month."""
    if orders.empty:
        return pd.DataFrame(columns=["month", "net_sales", "orders"])
    frame = orders.assign(month=orders["order_date"].dt.to_period("M").dt.to_timestamp())
    return frame.groupby("month").agg(
        net_sales=("net_sales", "sum"), orders=("order_id", "nunique")
    ).reset_index().sort_values("month")


def aggregate_orders(orders: pd.DataFrame, field: str) -> pd.DataFrame:
    """Summarize selected orders by a dimension for charts and tables."""
    if field not in orders:
        raise DashboardDataError(f"Cannot summarize missing field: {field}")
    if orders.empty:
        return pd.DataFrame(columns=[field, "orders", "quantity_sold", "net_sales"])
    result = orders.groupby(field, dropna=False).agg(
        orders=("order_id", "nunique"),
        quantity_sold=("quantity", "sum"),
        net_sales=("net_sales", "sum"),
    ).reset_index()
    result["average_order_value"] = result["net_sales"].div(
        result["orders"].replace(0, pd.NA)
    )
    total_revenue = result["net_sales"].sum()
    result["revenue_contribution"] = (
        result["net_sales"].div(total_revenue) if total_revenue else 0.0
    )
    return result.sort_values("net_sales", ascending=False)


def product_performance(
    orders: pd.DataFrame,
    products: pd.DataFrame,
    categories: list[str] | None = None,
) -> pd.DataFrame:
    """Return selected-period product revenue and quantity, including zero-sales items."""
    catalog = products.copy()
    if categories is not None:
        catalog = catalog[catalog["category"].isin(categories)]
    totals = orders.groupby("product_id").agg(
        quantity_sold=("quantity", "sum"),
        net_sales=("net_sales", "sum"),
    )
    stale_columns = [
        "quantity_sold", "net_sales", "product_total_quantity", "product_total_revenue"
    ]
    result = catalog.drop(columns=stale_columns, errors="ignore").merge(
        totals, left_on="product_id", right_index=True, how="left"
    )
    result[["quantity_sold", "net_sales"]] = result[[
        "quantity_sold", "net_sales"
    ]].fillna(0)
    result["product_total_quantity"] = result["quantity_sold"]
    result["product_total_revenue"] = result["net_sales"]
    total_revenue = result["net_sales"].sum()
    result["revenue_contribution"] = (
        result["net_sales"] / total_revenue if total_revenue else 0.0
    )
    return result.sort_values("net_sales", ascending=False)


def customer_performance(orders: pd.DataFrame) -> pd.DataFrame:
    """Return selected-period customer revenue and unique order frequency."""
    fields = ["customer_id", "value_segment"]
    if orders.empty:
        return pd.DataFrame(columns=[*fields, "orders", "net_sales", "average_order_value"])
    result = orders.groupby(fields, dropna=False).agg(
        orders=("order_id", "nunique"), net_sales=("net_sales", "sum")
    ).reset_index()
    result["average_order_value"] = result["net_sales"].div(
        result["orders"].replace(0, pd.NA)
    )
    return result.sort_values("net_sales", ascending=False)


def customer_frequency(orders: pd.DataFrame) -> pd.DataFrame:
    """Count customers at each unique-order frequency in the selected window."""
    if orders.empty:
        return pd.DataFrame(columns=["order_frequency", "customers"])
    frequency = orders.groupby("customer_id")["order_id"].nunique()
    return frequency.value_counts().sort_index().rename_axis(
        "order_frequency"
    ).reset_index(name="customers")


def customer_revenue_distribution(orders: pd.DataFrame) -> pd.DataFrame:
    """Count active customers in equal-width bands of selected-period revenue."""
    summary = customer_performance(orders)
    if summary.empty:
        return pd.DataFrame(columns=["revenue_band", "customers"])
    distinct_values = max(1, int(summary["net_sales"].nunique()))
    band_count = min(10, distinct_values)
    bands = pd.cut(summary["net_sales"], bins=band_count, include_lowest=True).astype(str)
    return bands.value_counts().sort_index().rename_axis(
        "revenue_band"
    ).reset_index(name="customers")


def segment_performance(orders: pd.DataFrame) -> pd.DataFrame:
    """Summarize selected-window activity for the descriptive value segments."""
    return aggregate_orders(orders, "value_segment").rename(
        columns={"value_segment": "customer_segment"}
    )


def discount_performance(orders: pd.DataFrame) -> pd.DataFrame:
    """Compare observed order metrics across discount-rate bands, not causality."""
    columns = [
        "discount_band", "orders", "average_order_value", "discount_amount", "net_sales"
    ]
    if orders.empty:
        return pd.DataFrame(columns=columns)
    discount_rate = orders["discount_amount"].div(
        orders["gross_sales"].where(orders["gross_sales"] != 0)
    ).fillna(0.0)
    bands = pd.cut(
        discount_rate.clip(lower=0, upper=1),
        bins=[-0.000001, 0, 0.05, 0.10, 0.20, 1.0],
        labels=["0%", ">0-5%", ">5-10%", ">10-20%", ">20%"],
        include_lowest=True,
    )
    result = orders.assign(discount_band=bands).groupby(
        "discount_band", observed=True, dropna=False
    ).agg(
        orders=("order_id", "nunique"),
        average_order_value=("order_value", "mean"),
        discount_amount=("discount_amount", "sum"),
        net_sales=("net_sales", "sum"),
    ).reset_index()
    return result