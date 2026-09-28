"""Reusable descriptive analysis and chart generation for cleaned sales data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
ANALYTICS_DIR = PROCESSED_DIR / "analytics"
FIGURES_DIR = PROJECT_ROOT / "reports" / "figures"
INPUT_FILES = {
    "customers": "customers_cleaned.csv",
    "products": "products_cleaned.csv",
    "orders": "orders_cleaned.csv",
}
EXPECTED_ORDER_COLUMNS = [
    "order_id", "order_date", "customer_id", "product_id", "quantity",
    "discount", "payment_method", "order_status", "gross_sales",
    "discount_amount", "net_sales",
]


def load_cleaned_data(data_dir: Path = PROCESSED_DIR) -> dict[str, pd.DataFrame]:
    """Load the cleaned tables and parse their date columns."""
    datasets = {}
    for name, filename in INPUT_FILES.items():
        path = data_dir / filename
        if not path.is_file():
            raise FileNotFoundError(f"Required cleaned dataset not found: {path}")
        datasets[name] = pd.read_csv(path)
    for frame, field in ((datasets["customers"], "signup_date"), (datasets["orders"], "order_date")):
        if field in frame.columns:
            frame[field] = pd.to_datetime(frame[field], errors="coerce")
    return datasets


def prepare_analysis_data(datasets: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return an order-level table enriched with product and customer fields."""
    orders = datasets["orders"].copy()
    products = datasets["products"].copy()
    customers = datasets["customers"].copy()
    for column in ["quantity", "discount", "gross_sales", "discount_amount", "net_sales"]:
        if column in orders:
            orders[column] = pd.to_numeric(orders[column], errors="coerce")
    if "unit_price" in products:
        products["unit_price"] = pd.to_numeric(products["unit_price"], errors="coerce")
    if "order_date" in orders:
        orders["order_date"] = pd.to_datetime(orders["order_date"], errors="coerce")
    enriched = orders.merge(products, on="product_id", how="left", validate="many_to_one", suffixes=("", "_product"))
    enriched = enriched.merge(customers, on="customer_id", how="left", validate="many_to_one", suffixes=("", "_customer"))
    return orders, enriched


def calculate_kpis(datasets: dict[str, pd.DataFrame], orders: pd.DataFrame) -> pd.DataFrame:
    """Calculate the requested project-level KPIs from order rows and dimensions."""
    net_sales = pd.to_numeric(orders.get("net_sales", pd.Series(dtype="float64")), errors="coerce")
    gross_sales = pd.to_numeric(orders.get("gross_sales", pd.Series(dtype="float64")), errors="coerce")
    discounts = pd.to_numeric(orders.get("discount_amount", pd.Series(dtype="float64")), errors="coerce")
    quantity = pd.to_numeric(orders.get("quantity", pd.Series(dtype="float64")), errors="coerce")
    total_orders = int(orders["order_id"].nunique()) if "order_id" in orders else 0
    return pd.DataFrame([{
        "total_orders": total_orders,
        "total_customers": int(datasets["customers"]["customer_id"].nunique()),
        "total_products": int(datasets["products"]["product_id"].nunique()),
        "total_quantity_sold": int(quantity.sum()),
        "gross_sales": float(gross_sales.sum()),
        "total_discount_amount": float(discounts.sum()),
        "net_sales": float(net_sales.sum()),
        "average_order_value": float(net_sales.sum() / total_orders) if total_orders else float("nan"),
    }])


def _aggregate(frame: pd.DataFrame, group_fields: list[str], output_name: str) -> pd.DataFrame:
    grouped = frame.groupby(group_fields, dropna=False).agg(
        orders=("order_id", "nunique"),
        quantity_sold=("quantity", "sum"),
        gross_sales=("gross_sales", "sum"),
        discount_amount=("discount_amount", "sum"),
        net_sales=("net_sales", "sum"),
    ).reset_index()
    grouped["average_order_value"] = grouped["net_sales"] / grouped["orders"].replace(0, pd.NA)
    total_revenue = grouped["net_sales"].sum()
    grouped["revenue_contribution"] = grouped["net_sales"] / total_revenue if total_revenue else pd.NA
    if output_name != "":
        grouped = grouped.rename(columns={group_fields[-1]: output_name})
    return grouped


def build_analysis_tables(datasets: dict[str, pd.DataFrame], orders: pd.DataFrame, enriched: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Build product, category, customer, and monthly summary tables."""
    product = _aggregate(enriched, ["product_id", "product_name"], "product_name")
    product = product.merge(enriched[["product_id", "category", "subcategory"]].drop_duplicates("product_id"), on="product_id", how="left")
    category = _aggregate(enriched, ["category"], "category")
    subcategory = _aggregate(enriched, ["subcategory"], "subcategory")

    customer = _aggregate(enriched, ["customer_id", "customer_name"], "customer_name")
    customer = customer.merge(enriched[["customer_id", "customer_segment", "customer_region"]].drop_duplicates("customer_id"), on="customer_id", how="left")
    segment = _aggregate(enriched, ["customer_segment"], "customer_segment")
    region = _aggregate(enriched, ["customer_region"], "customer_region")

    monthly = orders.dropna(subset=["order_date"]).copy()
    monthly["month"] = monthly["order_date"].dt.to_period("M").dt.to_timestamp()
    monthly = monthly.groupby("month").agg(
        orders=("order_id", "nunique"),
        quantity_sold=("quantity", "sum"),
        gross_sales=("gross_sales", "sum"),
        discount_amount=("discount_amount", "sum"),
        net_sales=("net_sales", "sum"),
    ).reset_index()
    monthly["average_order_value"] = monthly["net_sales"] / monthly["orders"].replace(0, pd.NA)
    previous_month_sales = monthly["net_sales"].shift(1)
    monthly["mom_revenue_growth"] = (monthly["net_sales"] - previous_month_sales) / previous_month_sales.where(previous_month_sales != 0)

    return {
        "products": product.sort_values("net_sales", ascending=False),
        "categories": category.sort_values("net_sales", ascending=False),
        "subcategories": subcategory.sort_values("net_sales", ascending=False),
        "customers": customer.sort_values("net_sales", ascending=False),
        "customer_segments": segment.sort_values("net_sales", ascending=False),
        "customer_regions": region.sort_values("net_sales", ascending=False),
        "monthly": monthly.sort_values("month"),
    }


def create_eda_summary(kpis: pd.DataFrame, tables: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """Create descriptive summaries directly from computed tables."""
    integer_kpis = {"total_orders", "total_customers", "total_products", "total_quantity_sold"}
    kpi_values = {}
    for key, value in kpis.iloc[0].to_dict().items():
        if pd.isna(value):
            kpi_values[key] = None
        elif key in integer_kpis:
            kpi_values[key] = int(value)
        else:
            kpi_values[key] = float(value)
    monthly = tables["monthly"]
    valid_growth = monthly.dropna(subset=["mom_revenue_growth"])
    return {
        "kpis": kpi_values,
        "major_trends": {
            "highest_net_sales_month": None if monthly.empty else monthly.loc[monthly["net_sales"].idxmax(), "month"].strftime("%Y-%m"),
            "lowest_net_sales_month": None if monthly.empty else monthly.loc[monthly["net_sales"].idxmin(), "month"].strftime("%Y-%m"),
            "positive_mom_growth_months": int((valid_growth["mom_revenue_growth"] > 0).sum()),
            "negative_mom_growth_months": int((valid_growth["mom_revenue_growth"] < 0).sum()),
            "months_with_valid_growth": int(len(valid_growth)),
        },
        "top_performing_categories": tables["categories"].head(5)[["category", "orders", "quantity_sold", "net_sales", "revenue_contribution"]].to_dict(orient="records"),
        "top_performing_products": tables["products"].head(10)[["product_id", "product_name", "net_sales", "quantity_sold", "revenue_contribution"]].to_dict(orient="records"),
        "customer_segment_patterns": tables["customer_segments"].to_dict(orient="records"),
        "regional_patterns": tables["customer_regions"].to_dict(orient="records"),
        "monthly_patterns": monthly.to_dict(orient="records"),
        "interpretation_note": "These are descriptive summaries of the provided cleaned sample. They are not statistical significance tests or causal conclusions.",
    }


def save_analysis_outputs(kpis: pd.DataFrame, tables: dict[str, pd.DataFrame], summary: dict[str, Any], output_dir: Path = ANALYTICS_DIR) -> None:
    """Write tabular analysis outputs as CSV and the structured narrative summary as JSON."""
    output_dir.mkdir(parents=True, exist_ok=True)
    kpis.to_csv(output_dir / "kpis.csv", index=False)
    tables["products"].to_csv(output_dir / "product_analysis.csv", index=False)
    tables["categories"].to_csv(output_dir / "category_analysis.csv", index=False)
    tables["subcategories"].to_csv(output_dir / "subcategory_analysis.csv", index=False)
    tables["customers"].to_csv(output_dir / "customer_analysis.csv", index=False)
    tables["customer_segments"].to_csv(output_dir / "customer_segment_analysis.csv", index=False)
    tables["customer_regions"].to_csv(output_dir / "customer_region_analysis.csv", index=False)
    tables["monthly"].to_csv(output_dir / "monthly_analysis.csv", index=False, date_format="%Y-%m-%d")
    (output_dir / "eda_summary.json").write_text(json.dumps(summary, indent=2, default=_json_default), encoding="utf-8")


def _json_default(value: Any) -> Any:
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if pd.isna(value):
        return None
    raise TypeError(f"Cannot serialize {type(value).__name__}")


def create_charts(tables: dict[str, pd.DataFrame], orders: pd.DataFrame, figures_dir: Path = FIGURES_DIR) -> list[Path]:
    """Create a focused set of labeled figures for the business questions."""
    figures_dir.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid", context="notebook", palette="deep")
    saved: list[Path] = []

    def save(fig: plt.Figure, filename: str) -> None:
        fig.tight_layout()
        path = figures_dir / filename
        fig.savefig(path, dpi=160, bbox_inches="tight")
        plt.close(fig)
        saved.append(path)

    monthly = tables["monthly"]
    fig, ax = plt.subplots(figsize=(10, 5))
    sns.lineplot(data=monthly, x="month", y="net_sales", marker="o", ax=ax, label="Net sales")
    ax.set(title="Monthly Net Sales", xlabel="Month", ylabel="Net sales")
    ax.tick_params(axis="x", rotation=45)
    ax.legend(title="Measure")
    save(fig, "monthly_net_sales.png")

    fig, ax = plt.subplots(figsize=(10, 5))
    sns.lineplot(data=monthly, x="month", y="orders", marker="o", color="#26734d", ax=ax, label="Orders")
    ax.set(title="Monthly Order Volume", xlabel="Month", ylabel="Number of orders")
    ax.tick_params(axis="x", rotation=45)
    ax.legend(title="Measure")
    save(fig, "monthly_orders.png")

    category = tables["categories"].sort_values("net_sales", ascending=False)
    fig, ax = plt.subplots(figsize=(10, 5))
    sns.barplot(data=category, x="net_sales", y="category", color="#3973ac", ax=ax)
    ax.set(title="Net Sales by Product Category", xlabel="Net sales", ylabel="Category")
    save(fig, "category_revenue.png")

    top_products = tables["products"].nlargest(10, "net_sales").sort_values("net_sales")
    fig, ax = plt.subplots(figsize=(10, 6))
    sns.barplot(data=top_products, x="net_sales", y="product_name", color="#d9853b", ax=ax)
    ax.set(title="Top 10 Products by Net Sales", xlabel="Net sales", ylabel="Product")
    save(fig, "top_products_revenue.png")

    segment = tables["customer_segments"].sort_values("net_sales", ascending=False)
    fig, ax = plt.subplots(figsize=(9, 5))
    sns.barplot(data=segment, x="customer_segment", y="net_sales", color="#7057a3", ax=ax)
    ax.set(title="Net Sales by Customer Segment", xlabel="Customer segment", ylabel="Net sales")
    ax.tick_params(axis="x", rotation=20)
    save(fig, "customer_segment_revenue.png")

    region = tables["customer_regions"].sort_values("net_sales", ascending=False)
    fig, ax = plt.subplots(figsize=(9, 5))
    sns.barplot(data=region, x="customer_region", y="net_sales", color="#3b8e91", ax=ax)
    ax.set(title="Net Sales by Customer Region", xlabel="Region", ylabel="Net sales")
    ax.tick_params(axis="x", rotation=20)
    save(fig, "regional_revenue.png")

    order_values = orders.groupby("order_id", dropna=False)["net_sales"].sum(min_count=1)
    values = pd.to_numeric(order_values, errors="coerce").dropna()
    fig, ax = plt.subplots(figsize=(9, 5))
    sns.histplot(values, bins=30, kde=True, color="#3973ac", ax=ax)
    ax.set(title="Distribution of Net Sales per Order", xlabel="Net sales per order", ylabel="Number of orders")
    save(fig, "order_value_distribution.png")

    return saved


def run_eda(data_dir: Path = PROCESSED_DIR, analytics_dir: Path = ANALYTICS_DIR, figures_dir: Path = FIGURES_DIR) -> dict[str, Any]:
    """Run loading, KPI and aggregate calculations, charting, and output writing."""
    datasets = load_cleaned_data(data_dir)
    orders, enriched = prepare_analysis_data(datasets)
    kpis = calculate_kpis(datasets, orders)
    tables = build_analysis_tables(datasets, orders, enriched)
    summary = create_eda_summary(kpis, tables)
    save_analysis_outputs(kpis, tables, summary, analytics_dir)
    figures = create_charts(tables, orders, figures_dir)
    summary["charts"] = [path.name for path in figures]
    (analytics_dir / "eda_summary.json").write_text(json.dumps(summary, indent=2, default=_json_default), encoding="utf-8")
    return {"datasets": datasets, "orders": orders, "enriched": enriched, "kpis": kpis, "tables": tables, "summary": summary, "figures": figures}


def main() -> int:
    """Command-line entry point for generating EDA tables and charts."""
    result = run_eda()
    print("EDA outputs generated")
    print(f"KPIs: {ANALYTICS_DIR / 'kpis.csv'}")
    print(f"Tables and summary: {ANALYTICS_DIR}")
    print(f"Charts: {FIGURES_DIR} ({len(result['figures'])} files)")
    print(f"Orders: {result['summary']['kpis']['total_orders']:,}")
    print(f"Net sales: {result['summary']['kpis']['net_sales']:,.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
