import re
import numpy as np
import pandas as pd

SHOPIFY_MAPPING = {
    "Name": "order_ref",
    "Created at": "ordered_at",
    "Financial Status": "financial_status",
    "Total": "total_amount",
    "Payment Method": "payment_method",
    "Lineitem name": "item_name",
    "Qty": "quantity",
    "SKU": "sku",
    "Shipping Name": "canonical_name",
    "Shipping City": "shipping_city",
    "Phone": "normalized_phone",
}

AMANA_MAPPING = {
    "Réf Client": "order_ref",
    "N° Colis": "tracking_number",
    "Statut": "raw_status",
    "Date Dépôt": "shipped_on",
    "Date Livraison": "delivered_on",
    "Ville Destinataire": "raw_city",
    "Montant COD": "cod_amount",
    "Motif Retour": "return_reason",
}

CARRIER2_MAPPING = {
    "tracking": "tracking_number",
    "status": "raw_status",
    "city": "raw_city",
}
CITY_MAPPING = {
    "casa": "Casablanca",
    "الدار البيضاء": "Casablanca",
    "dar el beida": "Casablanca",
    "lyon": "Lyon",
}


def normalize_phone(phone):
    if pd.isna(phone):
        return np.nan

    cleaned = re.sub(r"[\s\-\(\)]", "", str(phone).strip())

    if cleaned.startswith("00"):
        cleaned = "+" + cleaned[2:]
    elif re.match(r"^0[567]\d{8}$", cleaned):
        cleaned = "+212" + cleaned[1:]
    elif re.match(r"^212[567]\d{8}$", cleaned):
        cleaned = "+" + cleaned

    if not re.match(r"^\+\d{9,15}$", cleaned):
        return np.nan

    return cleaned


def extract_country_code(phone):
    if pd.isna(phone):
        return np.nan
    match = re.match(r"^(\+\d{1,3})", str(phone))
    return match.group(1) if match else np.nan


def clean_customers(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = df.copy()
    cleaned["canonical_name"] = (
        cleaned["canonical_name"]
        .astype(str)
        .str.strip()
        .str.upper()
        .replace({"NAN": np.nan, "NONE": np.nan, "": np.nan})
    )
    cleaned["normalized_phone"] = cleaned["normalized_phone"].apply(normalize_phone)
    cleaned["country_code"] = cleaned["normalized_phone"].apply(extract_country_code)

    if "shipping_city" in cleaned.columns:
        cleaned["normalized_city"] = (
            cleaned["shipping_city"]
            .astype(str)
            .str.strip()
            .str.lower()
            .replace(CITY_MAPPING)
            .str.title()
            .replace({"Nan": np.nan, "None": np.nan, "": np.nan})
        )
    else:
        cleaned["normalized_city"] = np.nan

    cleaned = cleaned.dropna(subset=["canonical_name"])
    with_phone = cleaned.dropna(subset=["normalized_phone"]).drop_duplicates(subset=["normalized_phone"])
    without_phone = cleaned[cleaned["normalized_phone"].isna()].drop_duplicates(subset=["canonical_name"])
    cleaned = pd.concat([with_phone, without_phone], ignore_index=True)

    return cleaned[["canonical_name", "normalized_phone", "normalized_city", "country_code"]]


def clean_products(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = df.copy()
    cleaned["sku"] = (
        cleaned["sku"]
        .astype(str)
        .str.strip()
        .str.upper()
        .replace({"NAN": np.nan, "NONE": np.nan, "": np.nan})
    )
    cleaned["product_name"] = (
        cleaned["item_name" if "item_name" in cleaned.columns else "product_name"]
        .astype(str)
        .str.strip()
        .str.lower()
        .replace({"nan": np.nan, "none": np.nan, "": np.nan})
    )

    cleaned = cleaned.dropna(subset=["sku", "product_name"])
    cleaned = cleaned.drop_duplicates(subset=["sku"])

    return cleaned[["sku", "product_name"]]


def clean_orders(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = df.copy()
    cleaned["order_ref"] = (
        cleaned["order_ref"]
        .astype(str)
        .str.strip()
        .str.lstrip("#")
        .str.strip()
        .replace({"nan": np.nan, "none": np.nan, "None": np.nan, "": np.nan})
    )

    cleaned["shipping_city"] = (
        cleaned["shipping_city"]
        .astype(str)
        .str.strip()
        .str.lower()
        .replace(CITY_MAPPING)
        .str.title()
        .replace({"Nan": np.nan, "None": np.nan, "": np.nan})
    )

    cleaned["ordered_at"] = pd.to_datetime(cleaned["ordered_at"], errors="coerce")
    cleaned["total_amount"] = pd.to_numeric(cleaned["total_amount"], errors="coerce").fillna(0.00)
    cleaned.loc[cleaned["total_amount"] < 0, "total_amount"] = 0.00

    for col in ["financial_status", "payment_method"]:
        if col in cleaned.columns:
            cleaned[col] = (
                cleaned[col]
                .astype(str)
                .str.strip()
                .str.lower()
                .replace({"nan": np.nan, "none": np.nan, "": np.nan})
            )
        else:
            cleaned[col] = np.nan

    if "normalized_phone" in cleaned.columns:
        cleaned["normalized_phone"] = cleaned["normalized_phone"].apply(normalize_phone)
    if "canonical_name" in cleaned.columns:
        cleaned["canonical_name"] = (
            cleaned["canonical_name"]
            .astype(str)
            .str.strip()
            .str.upper()
            .replace({"NAN": np.nan, "NONE": np.nan, "": np.nan})
        )

    cleaned = cleaned.dropna(subset=["order_ref", "ordered_at"])
    cleaned = cleaned.drop_duplicates(subset=["order_ref"])

    cols = [
        "order_ref",
        "ordered_at",
        "financial_status",
        "payment_method",
        "shipping_city",
        "total_amount",
        "normalized_phone",
        "canonical_name",
    ]
    return cleaned[[c for c in cols if c in cleaned.columns]]


def clean_order_items(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = df.copy()
    cleaned["order_ref"] = (
        cleaned["order_ref"]
        .astype(str)
        .str.strip()
        .str.lstrip("#")
        .str.strip()
        .replace({"nan": np.nan, "none": np.nan, "None": np.nan, "": np.nan})
    )
    cleaned["sku"] = (
        cleaned["sku"]
        .astype(str)
        .str.strip()
        .str.upper()
        .replace({"NAN": np.nan, "NONE": np.nan, "": np.nan})
    )
    cleaned["item_name"] = (
        cleaned["item_name"]
        .astype(str)
        .str.strip()
        .str.lower()
        .replace({"nan": np.nan, "none": np.nan, "": np.nan})
    )

    cleaned["quantity"] = pd.to_numeric(cleaned["quantity"], errors="coerce")
    cleaned = cleaned.dropna(subset=["order_ref", "item_name", "quantity"])
    cleaned = cleaned[cleaned["quantity"] > 0].copy()
    cleaned["quantity"] = cleaned["quantity"].astype(int)

    return cleaned[["order_ref", "sku", "item_name", "quantity"]]


def clean_shipments(df: pd.DataFrame, dayfirst: bool = False) -> pd.DataFrame:
    cleaned = df.copy()

    cleaned["order_ref"] = (
        cleaned["order_ref"]
        .astype(str)
        .str.strip()
        .str.lstrip("#")
        .str.strip()
        .replace({"nan": np.nan, "none": np.nan, "None": np.nan, "": np.nan})
    )

    cleaned["carrier_name"] = (
        cleaned["carrier_name"]
        .astype(str)
        .str.strip()
        .str.lower()
        .replace({"nan": np.nan, "none": np.nan, "None": np.nan, "": np.nan})
    )

    cleaned["tracking_number"] = (
        cleaned["tracking_number"]
        .astype(str)
        .str.strip()
        .str.lstrip("#")
        .str.strip()
        .replace({"nan": np.nan, "none": np.nan, "None": np.nan, "": np.nan})
    )

    if "raw_city" in cleaned.columns:
        cleaned["raw_city"] = (
            cleaned["raw_city"]
            .astype(str)
            .str.strip()
            .replace({"nan": np.nan, "none": np.nan, "None": np.nan, "": np.nan})
        )
        cleaned["normalized_city"] = (
            cleaned["raw_city"]
            .astype(str)
            .str.strip()
            .str.lower()
            .replace(CITY_MAPPING)
            .str.title()
            .replace({"Nan": np.nan, "None": np.nan, "": np.nan})
        )
    else:
        cleaned["raw_city"] = np.nan
        cleaned["normalized_city"] = np.nan

    if "cod_amount" in cleaned.columns:
        cleaned["cod_amount"] = (
            cleaned["cod_amount"]
            .astype(str)
            .str.strip()
            .str.replace(",", ".", regex=False)
        )
        cleaned["cod_amount"] = pd.to_numeric(cleaned["cod_amount"], errors="coerce").fillna(0.00)
    else:
        cleaned["cod_amount"] = 0.00

    STATUS_MAPPING = {
        "livré": "delivered",
        "delivered": "delivered",
        "en cours": "in_transit",
        "in transit": "in_transit",
        "retourné": "returned",
        "returned": "returned",
    }

    cleaned["raw_status"] = (
        cleaned["raw_status"]
        .astype(str)
        .str.strip()
        .replace({"nan": np.nan, "none": np.nan, "None": np.nan, "": np.nan})
    )

    cleaned["normalized_status"] = (
        cleaned["raw_status"]
        .astype(str)
        .str.strip()
        .str.lower()
        .replace(STATUS_MAPPING)
        .replace({"nan": np.nan, "none": np.nan, "None": np.nan, "": np.nan})
    )

    for col in ["return_reason", "notes"]:
        if col in cleaned.columns:
            cleaned[col] = (
                cleaned[col]
                .astype(str)
                .str.strip()
                .replace({"nan": np.nan, "none": np.nan, "None": np.nan, "": np.nan})
            )
        else:
            cleaned[col] = np.nan

    cleaned["shipped_on"] = pd.to_datetime(cleaned["shipped_on"], dayfirst=dayfirst, errors="coerce").dt.date
    cleaned["delivered_on"] = pd.to_datetime(cleaned["delivered_on"], dayfirst=dayfirst, errors="coerce").dt.date

    cleaned = cleaned.dropna(subset=["tracking_number", "carrier_name", "normalized_status"])

    return cleaned[
        [
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
    ]
    
STOCK_MAPPING = {
    "SKU": "sku",
    "Produit": "product_name",
    "Coopérative": "cooperative_name",
    "Qté stock": "available_stock",
    "Coût achat (MAD)": "current_unit_cost",
    "Date réappro": "last_restock_date",
    "Remarque": "notes",
}


def clean_stock(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = df.copy()

    cleaned["sku"] = (
        cleaned["sku"]
        .astype(str)
        .str.strip()
        .str.upper()
        .replace({"NAN": np.nan, "NONE": np.nan, "": np.nan})
    )

    cleaned["product_name"] = (
        cleaned["product_name"]
        .astype(str)
        .str.strip()
        .str.lower()
        .replace({"nan": np.nan, "none": np.nan, "": np.nan})
    )

    cleaned["cooperative_name"] = (
        cleaned["cooperative_name"]
        .astype(str)
        .str.strip()
        .replace({"nan": np.nan, "none": np.nan, "None": np.nan, "": np.nan})
    )

    cleaned["available_stock"] = pd.to_numeric(cleaned["available_stock"], errors="coerce").fillna(0).astype(int)
    cleaned["current_unit_cost"] = pd.to_numeric(cleaned["current_unit_cost"], errors="coerce")
    cleaned["last_restock_date"] = pd.to_datetime(cleaned["last_restock_date"], dayfirst=True, errors="coerce")

    cleaned["notes"] = (
        cleaned["notes"]
        .astype(str)
        .str.strip()
        .replace({"nan": np.nan, "none": np.nan, "None": np.nan, "": np.nan})
    )

    cleaned = cleaned.dropna(subset=["sku"])

    # Sort by restock date so the latest valid cost/name/cooperative wins
    cleaned = cleaned.sort_values(by="last_restock_date", na_position="first")

    def last_valid(series):
        valid = series.dropna()
        return valid.iloc[-1] if not valid.empty else np.nan

    def join_notes(series):
        valid = series.dropna().unique()
        return " | ".join(valid) if len(valid) > 0 else np.nan

    aggregated = cleaned.groupby("sku", as_index=False).agg(
        product_name=("product_name", last_valid),
        cooperative_name=("cooperative_name", last_valid),
        available_stock=("available_stock", "sum"),
        current_unit_cost=("current_unit_cost", last_valid),
        last_restock_date=("last_restock_date", last_valid),
        notes=("notes", join_notes),
    )

    aggregated["current_unit_cost"] = aggregated["current_unit_cost"].fillna(0.00)
    aggregated["cooperative_name"] = aggregated["cooperative_name"].fillna("غير محدد")
    aggregated["last_restock_date"] = pd.to_datetime(aggregated["last_restock_date"]).dt.date

    return aggregated[
        [
            "sku",
            "product_name",
            "cooperative_name",
            "available_stock",
            "current_unit_cost",
            "last_restock_date",
            "notes",
        ]
    ]