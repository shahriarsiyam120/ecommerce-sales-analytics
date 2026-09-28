"""Interactive Streamlit dashboard for the persisted advanced analytics layer."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.data_access import (  # noqa: E402
    aggregate_orders,
    calculate_kpis,
    customer_frequency,
    customer_performance,
    customer_revenue_distribution,
    discount_performance,
    filter_orders,
    get_date_bounds,
    get_filter_options,
    load_dashboard_data,
    monthly_performance,
    product_performance,
    segment_performance,
)


st.set_page_config(
    page_title="Commerce Intelligence",
    page_icon=":material/monitoring:",
    layout="wide",
)


@st.cache_data(ttl=300)
def load_data() -> dict[str, pd.DataFrame]:
    return load_dashboard_data()


def _format_number(value: int | float, decimals: int = 0) -> str:
    return f"{value:,.{decimals}f}"


def _show_chart(title: str, frame: pd.DataFrame, x: str, y: str, chart: str = "bar") -> None:
    st.subheader(title)
    if frame.empty or y not in frame or frame[y].dropna().empty:
        st.info("No records for the current selection.")
        return
    if chart == "line":
        st.line_chart(frame, x=x, y=y)
    else:
        st.bar_chart(frame, x=x, y=y)


def _show_table(title: str, frame: pd.DataFrame) -> None:
    st.subheader(title)
    if frame.empty:
        st.info("No records for the current selection.")
        return
    column_config = {
        "net_sales": st.column_config.NumberColumn("Net revenue", format="%,.2f"),
        "customer_total_revenue": st.column_config.NumberColumn(
            "Historical revenue", format="%,.2f"
        ),
        "quantity_sold": st.column_config.NumberColumn("Quantity sold", format="%,.0f"),
        "product_total_quantity": st.column_config.NumberColumn(
            "Quantity sold", format="%,.0f"
        ),
        "product_total_revenue": st.column_config.NumberColumn(
            "Net revenue", format="%,.2f"
        ),
        "revenue_contribution": st.column_config.NumberColumn(
            "Revenue share", format="percent"
        ),
        "average_order_value": st.column_config.NumberColumn(
            "Average order value", format="%,.2f"
        ),
    }
    st.dataframe(frame, column_config=column_config, hide_index=True)


def _sidebar(
    data: dict[str, pd.DataFrame],
) -> tuple[dict[str, list[str]], tuple[object, ...] | None]:
    orders = data["orders"]
    options = get_filter_options(orders)
    bounds = get_date_bounds(orders)
    with st.sidebar:
        st.title("Commerce intelligence")
        st.caption("Filter the observed order history")
        selected_range = None
        if bounds:
            selected_range = st.date_input(
                "Date range", value=bounds, min_value=bounds[0], max_value=bounds[1]
            )
        selections = {
            "regions": st.multiselect(
                "Region",
                options.get("regions", []),
                default=options.get("regions", []),
            ),
            "customer_segments": st.multiselect(
                "Customer value segment",
                options.get("customer_segments", []),
                default=options.get("customer_segments", []),
            ),
            "categories": st.multiselect(
                "Category", options.get("categories", []), default=options.get("categories", [])
            ),
            "order_statuses": st.multiselect(
                "Order status",
                options.get("order_statuses", []),
                default=options.get("order_statuses", []),
            ),
            "payment_methods": st.multiselect(
                "Payment method",
                options.get("payment_methods", []),
                default=options.get("payment_methods", []),
            ),
        }
    if selected_range and len(selected_range) == 2:
        return selections, selected_range
    return selections, None


def main() -> None:
    st.title("E-commerce sales analytics")
    st.caption("Descriptive performance across the available order history")
    try:
        data = load_data()
    except (OSError, ValueError, pd.errors.ParserError) as exc:
        st.error(f"Dashboard data could not be loaded: {exc}")
        st.info(
            "Run cleaning, then `python -m src.analytics.advanced_analytics` "
            "from the repository root."
        )
        st.stop()

    selections, date_range = _sidebar(data)
    start_date, end_date = date_range if date_range else (None, None)
    selected_orders = filter_orders(
        data["orders"],
        start_date=start_date,
        end_date=end_date,
        **selections,
    )
    selected_products = data["products"]
    if selections["categories"] is not None:
        selected_products = selected_products[
            selected_products["category"].isin(selections["categories"])
        ]
    kpis = calculate_kpis(selected_orders, selected_products)

    st.caption(
        "Revenue and customer segments describe the observed history; "
        "discount comparisons are not causal."
    )
    metric_specs = [
        ("Total revenue", kpis["total_revenue"], 2),
        ("Total orders", kpis["total_orders"], 0),
        ("Customers in selection", kpis["total_customers"], 0),
        ("Products in catalog", kpis["total_products"], 0),
        ("Quantity sold", kpis["total_quantity"], 0),
        ("Average order value", kpis["average_order_value"], 2),
    ]
    for row_start in (0, 3):
        columns = st.columns(3)
        for column, (label, value, precision) in zip(
            columns, metric_specs[row_start : row_start + 3]
        ):
            column.metric(label, _format_number(value, precision), border=True)
    st.caption("Revenue is shown in the source dataset's currency units.")

    if selected_orders.empty:
        st.info(
            "No orders match these filters. Adjust the date range or clear "
            "one or more selections."
        )
        return

    view = st.segmented_control(
        "Analysis",
        options=["Executive overview", "Sales", "Products", "Customers"],
        default="Executive overview",
    )
    if view == "Executive overview":
        monthly = monthly_performance(selected_orders)
        left, right = st.columns(2)
        with left:
            _show_chart("Revenue trend", monthly, "month", "net_sales", chart="line")
        with right:
            _show_chart("Orders trend", monthly, "month", "orders", chart="line")
        st.subheader("Selected-period snapshot")
        _show_table("Top categories", aggregate_orders(selected_orders, "category").head(8))
    elif view == "Sales":
        monthly = monthly_performance(selected_orders)
        left, right = st.columns(2)
        with left:
            _show_chart("Monthly revenue", monthly, "month", "net_sales", chart="line")
            _show_chart(
                "Revenue by category",
                aggregate_orders(selected_orders, "category"),
                "category",
                "net_sales",
            )
            _show_chart(
                "Revenue by region",
                aggregate_orders(selected_orders, "customer_region"),
                "customer_region",
                "net_sales",
            )
            _show_chart(
                "Revenue by discount band",
                discount_performance(selected_orders),
                "discount_band",
                "net_sales",
            )
        with right:
            _show_chart("Monthly orders", monthly, "month", "orders", chart="line")
            _show_chart(
                "Payment method",
                aggregate_orders(selected_orders, "payment_method"),
                "payment_method",
                "net_sales",
            )
            _show_chart(
                "Order status",
                aggregate_orders(selected_orders, "order_status"),
                "order_status",
                "orders",
            )
    elif view == "Products":
        performance = product_performance(
            selected_orders, data["products"], categories=selections["categories"]
        )
        left, right = st.columns(2)
        with left:
            _show_chart(
                "Top products by revenue", performance.head(10), "product_name", "net_sales"
            )
            _show_chart(
                "Category revenue contribution",
                aggregate_orders(selected_orders, "category"),
                "category",
                "net_sales",
            )
        with right:
            _show_chart(
                "Top products by quantity",
                performance.nlargest(10, "quantity_sold"),
                "product_name",
                "quantity_sold",
            )
            _show_chart(
                "Subcategory revenue",
                aggregate_orders(selected_orders, "subcategory"),
                "subcategory",
                "net_sales",
            )
        _show_table("Product performance", performance)
        _show_table("Lowest revenue products", performance.tail(10).sort_values("net_sales"))
    elif view == "Customers":
        customer_summary = customer_performance(selected_orders)
        revenue_distribution = customer_revenue_distribution(selected_orders)
        segments = segment_performance(selected_orders)
        frequency = customer_frequency(selected_orders)
        left, right = st.columns(2)
        with left:
            _show_chart(
                "Revenue by value segment", segments, "customer_segment", "net_sales"
            )
            _show_chart(
                "Customer order frequency", frequency, "order_frequency", "customers"
            )
        with right:
            _show_chart(
                "Customer revenue distribution",
                revenue_distribution,
                "revenue_band",
                "customers",
            )
            _show_table("Top customers", customer_summary.head(20))
        _show_table("Customer order frequency", frequency)


main()