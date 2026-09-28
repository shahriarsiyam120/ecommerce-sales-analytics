USE ecommerce_analytics;

-- What are revenue, order count, and average order value for each customer?
SELECT
    c.customer_id,
    c.customer_name,
    COUNT(DISTINCT o.order_id) AS order_count,
    COALESCE(SUM(o.net_sales), 0) AS net_sales,
    COALESCE(SUM(o.net_sales) / NULLIF(COUNT(DISTINCT o.order_id), 0), 0) AS average_order_value
FROM customers AS c
LEFT JOIN `orders` AS o ON o.customer_id = c.customer_id
GROUP BY c.customer_id, c.customer_name
ORDER BY net_sales DESC, c.customer_id;

-- Which customers have generated the highest net sales?
SELECT
    c.customer_id,
    c.customer_name,
    c.customer_segment,
    c.customer_region,
    COUNT(DISTINCT o.order_id) AS order_count,
    SUM(o.net_sales) AS net_sales
FROM customers AS c
JOIN `orders` AS o ON o.customer_id = c.customer_id
GROUP BY c.customer_id, c.customer_name, c.customer_segment, c.customer_region
ORDER BY net_sales DESC
LIMIT 10;

-- Which customers have placed the most orders?
SELECT
    c.customer_id,
    c.customer_name,
    COUNT(DISTINCT o.order_id) AS order_count,
    SUM(o.net_sales) AS net_sales
FROM customers AS c
JOIN `orders` AS o ON o.customer_id = c.customer_id
GROUP BY c.customer_id, c.customer_name
HAVING COUNT(DISTINCT o.order_id) > 0
ORDER BY order_count DESC, net_sales DESC
LIMIT 10;

-- What is average customer revenue when customers with no orders count as zero?
WITH customer_revenue AS (
    SELECT
        c.customer_id,
        COALESCE(SUM(o.net_sales), 0) AS net_sales
    FROM customers AS c
    LEFT JOIN `orders` AS o ON o.customer_id = c.customer_id
    GROUP BY c.customer_id
)
SELECT AVG(net_sales) AS average_customer_revenue
FROM customer_revenue;

-- How do customer segments compare on order count, sales, and average order value?
SELECT
    c.customer_segment,
    COUNT(DISTINCT c.customer_id) AS customers,
    COUNT(DISTINCT o.order_id) AS total_orders,
    SUM(o.net_sales) AS net_sales,
    SUM(o.net_sales) / NULLIF(COUNT(DISTINCT o.order_id), 0) AS average_order_value
FROM customers AS c
LEFT JOIN `orders` AS o ON o.customer_id = c.customer_id
GROUP BY c.customer_segment
ORDER BY net_sales DESC;

-- How do customer regions compare on order count, sales, and average order value?
SELECT
    c.customer_region,
    COUNT(DISTINCT c.customer_id) AS customers,
    COUNT(DISTINCT o.order_id) AS total_orders,
    SUM(o.net_sales) AS net_sales,
    SUM(o.net_sales) / NULLIF(COUNT(DISTINCT o.order_id), 0) AS average_order_value
FROM customers AS c
LEFT JOIN `orders` AS o ON o.customer_id = c.customer_id
GROUP BY c.customer_region
ORDER BY net_sales DESC;

-- How do customers rank by net sales, including ties?
WITH customer_revenue AS (
    SELECT
        c.customer_id,
        c.customer_name,
        COALESCE(SUM(o.net_sales), 0) AS net_sales
    FROM customers AS c
    LEFT JOIN `orders` AS o ON o.customer_id = c.customer_id
    GROUP BY c.customer_id, c.customer_name
)
SELECT
    customer_id,
    customer_name,
    net_sales,
    100.0 * net_sales / NULLIF(SUM(net_sales) OVER (), 0) AS revenue_contribution_pct,
    RANK() OVER (ORDER BY net_sales DESC) AS revenue_rank,
    ROW_NUMBER() OVER (ORDER BY net_sales DESC, customer_id) AS revenue_row_number
FROM customer_revenue
ORDER BY revenue_rank, customer_id;
