# Plaid's own category labels mapped onto our categories (detailed label first, then primary).
PFC_DETAILED = {
    "FOOD_AND_DRINK_GROCERIES": "Groceries",
    "LOAN_PAYMENTS_CREDIT_CARD_PAYMENT": "Transfer",
    "LOAN_PAYMENTS_MORTGAGE_PAYMENT": "Housing",
    "RENT_AND_UTILITIES_RENT": "Housing",
}
PFC_PRIMARY = {
    "INCOME": "Income", "TRANSFER_IN": "Transfer", "TRANSFER_OUT": "Transfer",
    "FOOD_AND_DRINK": "Dining", "GENERAL_MERCHANDISE": "Shopping", "ENTERTAINMENT": "Entertainment",
    "TRANSPORTATION": "Transport", "TRAVEL": "Travel", "MEDICAL": "Health", "PERSONAL_CARE": "Health",
    "RENT_AND_UTILITIES": "Utilities", "HOME_IMPROVEMENT": "Housing", "LOAN_PAYMENTS": "Other",
    "BANK_FEES": "Other", "GENERAL_SERVICES": "Other", "GOVERNMENT_AND_NON_PROFIT": "Other",
}


def categorize(conn, description, payload=None):
    """Returns (category_id or None, is_transfer). Your rules win; Plaid's category is the fallback."""
    text = (description or "").lower()
    for r in conn.execute("SELECT pattern, category_id FROM rules ORDER BY priority, id"):
        if r["pattern"].lower() in text:
            return r["category_id"], 0
    pfc = (payload or {}).get("personal_finance_category") or {}
    name = PFC_DETAILED.get(pfc.get("detailed")) or PFC_PRIMARY.get(pfc.get("primary"))
    if name:
        row = conn.execute("SELECT id FROM categories WHERE name=?", (name,)).fetchone()
        if row:
            return row["id"], int(name == "Transfer")
    return None, 0
