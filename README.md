# Diyar Market — E-Commerce ETL Data Pipeline

An end-to-end, idempotent ETL pipeline built with **Python (Pandas, Psycopg2)** and **PostgreSQL** to consolidate fragmented e-commerce data for **Diyar Market**, a Moroccan artisanal online store.

## Problem Solved
E-commerce operations often suffer from disconnected data across sales platforms, logistics partners, and manual inventory sheets. This pipeline automates extraction, standardization, deduplication, and relational loading from three disparate sources:
1. **Shopify Orders (`shopify_orders.csv`):** Orders, line items, and customer contact details.
2. **Shipping Carriers (`amana.csv` & `carrier2.csv`):** Multi-format tracking logs with inconsistent delimiters (`;` vs `,`), date formats (`DD/MM/YYYY` vs `YYYY-MM-DD`), and status labels.
3. **Inventory & Cost Catalog (`stock_export_*.csv`):** Google Sheets stock exports containing duplicate SKUs, retroactive cost updates, and cooperative details.

## Architecture & Data Model
- **Transform (`transform/clean_data.py`):**
  - Standardizes Moroccan and international phone numbers to E.164 format (`+212...`) to deduplicate customer profiles.
  - Normalizes city names (e.g., `casa`, `Dar el Beida` → `Casablanca`), order references (`#3041` → `3041`), and shipment statuses.
  - Aggregates duplicate inventory SKUs by summing stock quantities and retaining the latest valid unit cost and cooperative name.
- **Load (`load/load_data.py`):**
  - Enforces referential integrity across 5 PostgreSQL tables (`products`, `customers`, `orders`, `order_items`, `shipments`) inside atomic transactions.
  - Infers unit selling prices and locks historical unit costs at order time (`unit_cost_at_order`) for accurate profit margin tracking.
- **Analytics (`sql/analytics_views.sql`):**
  - Pre-built SQL views for product profitability, per-order margins, carrier return rates, city delivery times, and unshipped order reconciliation.

## Setup & Execution

### 1. Clone & Install Dependencies
```bash
git clone [https://github.com/exora999/diyar-market-pipeline.git](https://github.com/exora999/diyar-market-pipeline.git)
cd diyar-market-pipeline
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
