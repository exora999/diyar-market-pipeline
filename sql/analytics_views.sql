CREATE OR REPLACE VIEW vw_product_profitability AS
SELECT
    p.sku,
    p.product_name,
    p.cooperative_name,
    p.available_stock,
    p.current_unit_cost,
    COALESCE(SUM(oi.quantity), 0) AS total_units_sold,
    COALESCE(SUM(oi.line_gross_sales), 0) AS total_revenue,
    COALESCE(SUM(oi.line_product_cost_at_order), 0) AS total_cost,
    COALESCE(SUM(oi.line_gross_sales - oi.line_product_cost_at_order), 0) AS gross_profit,
    CASE
        WHEN COALESCE(SUM(oi.line_gross_sales), 0) > 0
        THEN ROUND((SUM(oi.line_gross_sales - oi.line_product_cost_at_order) / SUM(oi.line_gross_sales)) * 100, 2)
        ELSE 0
    END AS profit_margin_pct
FROM products p
LEFT JOIN order_items oi ON p.sku = oi.sku
GROUP BY p.sku, p.product_name, p.cooperative_name, p.available_stock, p.current_unit_cost
ORDER BY gross_profit DESC;

CREATE OR REPLACE VIEW vw_order_margins AS
SELECT
    o.order_ref,
    o.ordered_at,
    c.canonical_name AS customer_name,
    o.shipping_city,
    o.total_amount AS order_total,
    COALESCE(SUM(oi.line_product_cost_at_order), 0) AS total_product_cost,
    (o.total_amount - COALESCE(SUM(oi.line_product_cost_at_order), 0)) AS net_order_margin
FROM orders o
LEFT JOIN customers c ON o.customer_id = c.customer_id
LEFT JOIN order_items oi ON o.order_ref = oi.order_ref
GROUP BY o.order_ref, o.ordered_at, c.canonical_name, o.shipping_city, o.total_amount
ORDER BY o.ordered_at DESC;

CREATE OR REPLACE VIEW vw_carrier_performance AS
SELECT
    carrier_name,
    COUNT(*) AS total_shipments,
    COUNT(*) FILTER (WHERE normalized_status = 'delivered') AS delivered_count,
    COUNT(*) FILTER (WHERE normalized_status = 'returned') AS returned_count,
    COUNT(*) FILTER (WHERE normalized_status = 'in_transit') AS in_transit_count,
    ROUND((COUNT(*) FILTER (WHERE normalized_status = 'returned')::numeric / COUNT(*)) * 100, 2) AS return_rate_pct,
    ROUND(AVG(delivery_days), 1) AS avg_delivery_days
FROM shipments
GROUP BY carrier_name;

CREATE OR REPLACE VIEW vw_city_delivery_stats AS
SELECT
    COALESCE(normalized_city, 'Unknown') AS city,
    COUNT(*) AS total_shipments,
    COUNT(*) FILTER (WHERE normalized_status = 'returned') AS returned_count,
    ROUND((COUNT(*) FILTER (WHERE normalized_status = 'returned')::numeric / COUNT(*)) * 100, 2) AS return_rate_pct,
    ROUND(AVG(delivery_days), 1) AS avg_delivery_days
FROM shipments
GROUP BY COALESCE(normalized_city, 'Unknown')
ORDER BY total_shipments DESC;

CREATE OR REPLACE VIEW vw_unshipped_or_missing_orders AS
SELECT
    o.order_ref,
    o.ordered_at,
    c.canonical_name,
    c.normalized_phone,
    o.shipping_city,
    o.total_amount,
    o.financial_status
FROM orders o
LEFT JOIN customers c ON o.customer_id = c.customer_id
LEFT JOIN shipments s ON o.order_ref = s.order_ref
WHERE s.shipment_id IS NULL;