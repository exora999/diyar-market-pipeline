import os
import sys
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

# Add project root to sys.path to import transform module
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from transform.clean_data import (
    AMANA_MAPPING,
    CARRIER2_MAPPING,
    SHOPIFY_MAPPING,
    STOCK_MAPPING,
    clean_customers,
    clean_order_items,
    clean_orders,
    clean_products,
    clean_shipments,
    clean_stock,
)

# PostgreSQL connection configuration
DB_CONFIG = {
    "dbname": "diyar_market",
    "user": "postgres",
    "password": os.getenv("DB_PASSWORD"), 
    "host": "localhost",
    "port": "5432",
}


def to_sql_none(df: pd.DataFrame) -> pd.DataFrame:
    """Convert NaN and NaT values to Python None for PostgreSQL NULL compatibility."""
    return df.astype(object).where(pd.notnull(df), None)


def infer_unit_prices(orders_df: pd.DataFrame, order_items_df: pd.DataFrame) -> dict:
    """Infer unit selling price per SKU from single-item orders."""
    item_counts = order_items_df.groupby("order_ref").size()
    single_item_orders = item_counts[item_counts == 1].index

    merged = pd.merge(
        order_items_df[order_items_df["order_ref"].isin(single_item_orders)],
        orders_df[["order_ref", "total_amount"]],
        on="order_ref",
        how="inner",
    )
    merged = merged[(merged["sku"].notna()) & (merged["quantity"] > 0) & (merged["total_amount"] > 0)].copy()
    merged["unit_price"] = (merged["total_amount"] / merged["quantity"]).round(2)

    return merged.groupby("sku")["unit_price"].last().to_dict()


def extract_and_transform(base_dir: str):
    """Extract raw CSV files and apply transformation functions."""
    raw_dir = os.path.join(base_dir, "data", "raw")

    # 1. Read and standardize column names
    dfs = pd.read_csv(os.path.join(raw_dir, "shopify_orders.csv")).rename(columns=SHOPIFY_MAPPING)

    df_amana = pd.read_csv(os.path.join(raw_dir, "amana.csv"), sep=";").rename(columns=AMANA_MAPPING)
    df_amana["carrier_name"] = "amana"

    df_carrier2 = pd.read_csv(os.path.join(raw_dir, "carrier2.csv")).rename(columns=CARRIER2_MAPPING)
    df_carrier2["carrier_name"] = "carrier2"

    df_stock = pd.read_csv(os.path.join(raw_dir, "stock_export_2026-11-23.csv")).rename(columns=STOCK_MAPPING)

    # 2. Apply cleaning functions
    customers_df = to_sql_none(clean_customers(dfs))
    products_df = to_sql_none(clean_products(dfs))
    stock_df = to_sql_none(clean_stock(df_stock))
    orders_df = to_sql_none(clean_orders(dfs))
    order_items_df = to_sql_none(clean_order_items(dfs))

    shipments_df = pd.concat(
        [
            clean_shipments(df_amana, dayfirst=True),
            clean_shipments(df_carrier2, dayfirst=False),
        ],
        ignore_index=True,
    )
    shipments_df = to_sql_none(shipments_df)

    return customers_df, products_df, stock_df, orders_df, order_items_df, shipments_df


def load_products(cur, stock_df: pd.DataFrame, shopify_products_df: pd.DataFrame):
    """Load stock catalog first, then insert any additional Shopify SKUs without overwriting stock data."""
    stock_cols = [
        "sku",
        "product_name",
        "cooperative_name",
        "available_stock",
        "current_unit_cost",
        "last_restock_date",
        "notes",
    ]
    stock_rows = list(stock_df[stock_cols].itertuples(index=False, name=None))
    if stock_rows:
        query_stock = """
            INSERT INTO products (
                sku, product_name, cooperative_name,
                available_stock, current_unit_cost, last_restock_date, notes
            )
            VALUES %s
            ON CONFLICT (sku) DO UPDATE
            SET product_name = EXCLUDED.product_name,
                cooperative_name = EXCLUDED.cooperative_name,
                available_stock = EXCLUDED.available_stock,
                current_unit_cost = EXCLUDED.current_unit_cost,
                last_restock_date = EXCLUDED.last_restock_date,
                notes = EXCLUDED.notes,
                updated_at = CURRENT_TIMESTAMP;
        """
        execute_values(cur, query_stock, stock_rows)

    shopify_rows = list(shopify_products_df[["sku", "product_name"]].itertuples(index=False, name=None))
    if shopify_rows:
        query_shopify = """
            INSERT INTO products (sku, product_name)
            VALUES %s
            ON CONFLICT (sku) DO NOTHING;
        """
        execute_values(cur, query_shopify, shopify_rows)

    print(f"✔ {len(stock_rows)} stock product(s) and {len(shopify_rows)} Shopify SKU(s) synced in 'products'.")


def load_customers(cur, customers_df: pd.DataFrame):
    """Load or update customers table and return ID lookup dictionaries."""
    phone_to_id = {}
    name_to_id = {}

    with_phone = customers_df[customers_df["normalized_phone"].notna()]
    for row in with_phone.itertuples(index=False):
        cur.execute(
            """
            INSERT INTO customers (canonical_name, normalized_phone, normalized_city, country_code)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (normalized_phone) DO UPDATE
            SET canonical_name = EXCLUDED.canonical_name,
                normalized_city = COALESCE(EXCLUDED.normalized_city, customers.normalized_city),
                country_code = COALESCE(EXCLUDED.country_code, customers.country_code)
            RETURNING customer_id;
            """,
            (row.canonical_name, row.normalized_phone, row.normalized_city, row.country_code),
        )
        phone_to_id[row.normalized_phone] = cur.fetchone()[0]

    without_phone = customers_df[customers_df["normalized_phone"].isna()]
    for row in without_phone.itertuples(index=False):
        cur.execute(
            """
            SELECT customer_id FROM customers
            WHERE canonical_name = %s AND normalized_phone IS NULL
            LIMIT 1;
            """,
            (row.canonical_name,),
        )
        existing = cur.fetchone()
        if existing:
            cust_id = existing[0]
        else:
            cur.execute(
                """
                INSERT INTO customers (canonical_name, normalized_phone, normalized_city, country_code)
                VALUES (%s, NULL, %s, NULL)
                RETURNING customer_id;
                """,
                (row.canonical_name, row.normalized_city),
            )
            cust_id = cur.fetchone()[0]
        name_to_id[row.canonical_name] = cust_id

    print(f"✔ {len(phone_to_id) + len(name_to_id)} customer(s) loaded/updated in 'customers'.")
    return phone_to_id, name_to_id


def load_orders(cur, orders_df: pd.DataFrame, phone_to_id: dict, name_to_id: dict):
    """Load or update orders table linked to customer_id."""
    df = orders_df.copy()

    df["customer_id"] = df["normalized_phone"].map(phone_to_id)
    missing_cust = df["customer_id"].isna()
    df.loc[missing_cust, "customer_id"] = df.loc[missing_cust, "canonical_name"].map(name_to_id)
    df = to_sql_none(df)

    cols = [
        "order_ref",
        "customer_id",
        "ordered_at",
        "financial_status",
        "payment_method",
        "shipping_city",
        "total_amount",
    ]
    rows = list(df[cols].itertuples(index=False, name=None))
    if not rows:
        return

    query = """
        INSERT INTO orders (
            order_ref, customer_id, ordered_at,
            financial_status, payment_method, shipping_city, total_amount
        )
        VALUES %s
        ON CONFLICT (order_ref) DO UPDATE
        SET customer_id = EXCLUDED.customer_id,
            ordered_at = EXCLUDED.ordered_at,
            financial_status = EXCLUDED.financial_status,
            payment_method = EXCLUDED.payment_method,
            shipping_city = EXCLUDED.shipping_city,
            total_amount = EXCLUDED.total_amount;
    """
    execute_values(cur, query, rows)
    print(f"✔ {len(rows)} order(s) loaded/updated in 'orders'.")


def load_order_items(
    cur,
    order_items_df: pd.DataFrame,
    valid_orders: set,
    sku_to_cost: dict,
    sku_to_price: dict,
):
    """Load order line items with unit selling price and unit cost at order time."""
    df = order_items_df[order_items_df["order_ref"].isin(valid_orders)].copy()
    if df.empty:
        return

    df["sku"] = df["sku"].apply(lambda x: x if x in sku_to_cost else None)
    df["unit_price"] = df["sku"].map(sku_to_price).fillna(0.00)
    df["unit_cost_at_order"] = df["sku"].map(sku_to_cost).fillna(0.00)
    df = to_sql_none(df)

    order_refs = df["order_ref"].unique().tolist()
    cur.execute("DELETE FROM order_items WHERE order_ref = ANY(%s);", (order_refs,))

    cols = ["order_ref", "sku", "item_name", "quantity", "unit_price", "unit_cost_at_order"]
    rows = list(df[cols].itertuples(index=False, name=None))
    query = """
        INSERT INTO order_items (
            order_ref, sku, item_name, quantity, unit_price, unit_cost_at_order
        )
        VALUES %s;
    """
    execute_values(cur, query, rows)
    print(f"✔ {len(rows)} item(s) loaded with cost & price in 'order_items'.")


def load_shipments(cur, shipments_df: pd.DataFrame, valid_orders: set):
    """Load unified carrier shipments with foreign key validation."""
    df = shipments_df.copy()
    if df.empty:
        return

    df["order_ref"] = df["order_ref"].apply(lambda x: x if x in valid_orders else None)
    df = to_sql_none(df)

    tracking_nums = df["tracking_number"].dropna().unique().tolist()
    if tracking_nums:
        cur.execute("DELETE FROM shipments WHERE tracking_number = ANY(%s);", (tracking_nums,))

    cols = [
        "tracking_number",
        "order_ref",
        "carrier_name",
        "shipped_on",
        "delivered_on",
        "raw_city",
        "normalized_city",
        "cod_amount",
        "raw_status",
        "normalized_status",
        "return_reason",
        "notes",
    ]
    rows = list(df[cols].itertuples(index=False, name=None))
    query = """
        INSERT INTO shipments (
            tracking_number, order_ref, carrier_name,
            shipped_on, delivered_on, raw_city, normalized_city,
            cod_amount, raw_status, normalized_status,
            return_reason, notes
        )
        VALUES %s;
    """
    execute_values(cur, query, rows)
    print(f"✔ {len(rows)} shipment(s) loaded in 'shipments'.")


def run_pipeline():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    customers_df, products_df, stock_df, orders_df, order_items_df, shipments_df = extract_and_transform(base_dir)
    sku_to_price = infer_unit_prices(orders_df, order_items_df)

    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            load_products(cur, stock_df, products_df)
            phone_to_id, name_to_id = load_customers(cur, customers_df)
            load_orders(cur, orders_df, phone_to_id, name_to_id)

            cur.execute("SELECT order_ref FROM orders;")
            valid_orders = {r[0] for r in cur.fetchall()}

            cur.execute("SELECT sku, current_unit_cost FROM products;")
            sku_to_cost = {r[0]: float(r[1]) for r in cur.fetchall()}

            load_order_items(cur, order_items_df, valid_orders, sku_to_cost, sku_to_price)
            load_shipments(cur, shipments_df, valid_orders)

        conn.commit()
        print("🎉 Full ETL Pipeline completed! Stock, costs, prices, orders, and shipments synced.")
    except Exception as e:
        conn.rollback()
        print(f"❌ Pipeline failed, transaction rolled back: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    run_pipeline()