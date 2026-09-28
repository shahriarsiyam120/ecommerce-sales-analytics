USE ecommerce_analytics;

-- What are the revenue and quantity totals for every product, including products with no orders?
SELECT
    p.product_id,
    p.product_name,
    p.category,
    p.subcategory,
    COALESCE(SUM(o.net_sales), 0) AS net_sales,
    COALESCE(SUM(o.quantity), 0) AS quantity_sold
FROM products AS p
LEFT JOIN `orders` AS o ON o.product_id = p.product_id
GROUP BY p.product_id, p.product_name, p.category, p.subcategory
ORDER BY net_sales DESC, p.product_id;

-- Which products have the highest total net sales?
SELECT
    p.product_id,
    p.product_name,
    p.category,
    SUM(o.net_sales) AS net_sales,
    SUM(o.quantity) AS quantity_sold
FROM products AS p
JOIN `orders` AS o ON o.product_id = p.product_id
GROUP BY p.product_id, p.product_name, p.category
ORDER BY net_sales DESC
LIMIT 10;

-- Which products have the highest total quantity sold?
SELECT
    p.product_id,
    p.product_name,
    p.category,
    SUM(o.quantity) AS quantity_sold,
    SUM(o.net_sales) AS net_sales
FROM products AS p
JOIN `orders` AS o ON o.product_id = p.product_id
GROUP BY p.product_id, p.product_name, p.category
ORDER BY quantity_sold DESC, net_sales DESC
LIMIT 10;

-- Which catalog products have the lowest net sales, including products with no orders?
SELECT
    p.product_id,
    p.product_name,
    p.category,
    COALESCE(SUM(o.net_sales), 0) AS net_sales,
    COALESCE(SUM(o.quantity), 0) AS quantity_sold
FROM products AS p
LEFT JOIN `orders` AS o ON o.product_id = p.product_id
GROUP BY p.product_id, p.product_name, p.category
ORDER BY net_sales ASC, p.product_id
LIMIT 10;

-- What share of total net sales does each product contribute?
WITH product_sales AS (
    SELECT
        p.product_id,
        p.product_name,
        p.category,
        COALESCE(SUM(o.net_sales), 0) AS net_sales
    FROM products AS p
    LEFT JOIN `orders` AS o ON o.product_id = p.product_id
    GROUP BY p.product_id, p.product_name, p.category
)
SELECT
    product_id,
    product_name,
    category,
    net_sales,
    100.0 * net_sales / NULLIF(SUM(net_sales) OVER (), 0) AS revenue_contribution_pct
FROM product_sales
ORDER BY revenue_contribution_pct DESC, product_id;

-- How does each revenue-generating product rank against others in its category?
WITH product_sales AS (
    SELECT
        p.product_id,
        p.product_name,
        p.category,
        SUM(o.net_sales) AS net_sales
    FROM products AS p
    JOIN `orders` AS o ON o.product_id = p.product_id
    GROUP BY p.product_id, p.product_name, p.category
    HAVING SUM(o.net_sales) > 0
)
SELECT
    product_id,
    product_name,
    category,
    net_sales,
    ROW_NUMBER() OVER (PARTITION BY category ORDER BY net_sales DESC, product_id) AS category_row_number,
    RANK() OVER (PARTITION BY category ORDER BY net_sales DESC) AS category_sales_rank
FROM product_sales
ORDER BY category, category_sales_rank, product_id;

-- How do categories rank by total net sales?
WITH category_sales AS (
    SELECT
        p.category,
        SUM(o.net_sales) AS net_sales
    FROM products AS p
    JOIN `orders` AS o ON o.product_id = p.product_id
    GROUP BY p.category
)
SELECT
    category,
    net_sales,
    RANK() OVER (ORDER BY net_sales DESC) AS category_sales_rank
FROM category_sales
ORDER BY category_sales_rank, category;
