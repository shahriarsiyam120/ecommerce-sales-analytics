USE ecommerce_analytics;

-- What are the headline counts, sales totals, and average order value?
SELECT
    (SELECT COUNT(DISTINCT order_id) FROM `orders`) AS total_orders,
    (SELECT COUNT(DISTINCT customer_id) FROM customers) AS total_customers,
    (SELECT COUNT(DISTINCT product_id) FROM products) AS total_products,
    (SELECT COALESCE(SUM(quantity), 0) FROM `orders`) AS total_quantity_sold,
    (SELECT COALESCE(SUM(gross_sales), 0) FROM `orders`) AS gross_sales,
    (SELECT COALESCE(SUM(discount_amount), 0) FROM `orders`) AS total_discount_amount,
    (SELECT COALESCE(SUM(net_sales), 0) FROM `orders`) AS net_sales,
    (SELECT COALESCE(SUM(net_sales) / NULLIF(COUNT(DISTINCT order_id), 0), 0) FROM `orders`) AS average_order_value;

-- Which product categories contribute the most sales and units?
SELECT
    p.category,
    COUNT(DISTINCT o.order_id) AS total_orders,
    SUM(o.quantity) AS quantity_sold,
    SUM(o.gross_sales) AS gross_sales,
    SUM(o.discount_amount) AS discount_amount,
    SUM(o.net_sales) AS net_sales
FROM `orders` AS o
JOIN products AS p ON p.product_id = o.product_id
GROUP BY p.category
ORDER BY net_sales DESC;

-- Which subcategories contribute the most net sales?
SELECT
    p.category,
    p.subcategory,
    COUNT(DISTINCT o.order_id) AS total_orders,
    SUM(o.quantity) AS quantity_sold,
    SUM(o.net_sales) AS net_sales
FROM `orders` AS o
JOIN products AS p ON p.product_id = o.product_id
GROUP BY p.category, p.subcategory
ORDER BY net_sales DESC;

-- How do sales vary across customer regions?
SELECT
    c.customer_region,
    COUNT(DISTINCT o.order_id) AS total_orders,
    SUM(o.quantity) AS quantity_sold,
    SUM(o.net_sales) AS net_sales
FROM `orders` AS o
JOIN customers AS c ON c.customer_id = o.customer_id
GROUP BY c.customer_region
ORDER BY net_sales DESC;

-- Which payment methods are associated with the most sales?
SELECT
    payment_method,
    COUNT(DISTINCT order_id) AS total_orders,
    SUM(net_sales) AS net_sales,
    SUM(discount_amount) AS discount_amount
FROM `orders`
GROUP BY payment_method
ORDER BY net_sales DESC;

-- How are order counts and sales distributed across order statuses?
SELECT
    order_status,
    COUNT(DISTINCT order_id) AS total_orders,
    SUM(net_sales) AS net_sales,
    SUM(quantity) AS quantity_sold
FROM `orders`
GROUP BY order_status
ORDER BY total_orders DESC;

-- How do sales and average order value compare across customer segments?
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
