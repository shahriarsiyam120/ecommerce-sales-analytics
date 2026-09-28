USE ecommerce_analytics;

-- How do order volume, units, sales, discounts, AOV, growth, and cumulative sales change by month?
WITH monthly_sales AS (
    SELECT
        DATE_FORMAT(order_date, '%Y-%m-01') AS month_start,
        COUNT(DISTINCT order_id) AS total_orders,
        SUM(quantity) AS quantity_sold,
        SUM(gross_sales) AS gross_sales,
        SUM(discount_amount) AS discount_amount,
        SUM(net_sales) AS net_sales
    FROM `orders`
    GROUP BY DATE_FORMAT(order_date, '%Y-%m-01')
),
monthly_comparison AS (
    SELECT
        month_start,
        total_orders,
        quantity_sold,
        gross_sales,
        discount_amount,
        net_sales,
        net_sales / NULLIF(total_orders, 0) AS average_order_value,
        LAG(net_sales) OVER (ORDER BY month_start) AS previous_month_net_sales,
        RANK() OVER (ORDER BY net_sales DESC) AS monthly_sales_rank,
        SUM(net_sales) OVER (
            ORDER BY month_start
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS cumulative_net_sales
    FROM monthly_sales
)
SELECT
    month_start,
    total_orders,
    quantity_sold,
    gross_sales,
    discount_amount,
    net_sales,
    average_order_value,
    monthly_sales_rank,
    CASE
        WHEN previous_month_net_sales IS NULL OR previous_month_net_sales = 0 THEN NULL
        ELSE (net_sales - previous_month_net_sales) / previous_month_net_sales
    END AS mom_revenue_growth,
    cumulative_net_sales
FROM monthly_comparison
ORDER BY month_start;
