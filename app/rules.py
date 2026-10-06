def categorize(conn, description):
    """First matching rule wins (lowest priority number). None = needs review."""
    text = (description or "").lower()
    for r in conn.execute("SELECT pattern, category_id FROM rules ORDER BY priority, id"):
        if r["pattern"].lower() in text:
            return r["category_id"]
    return None
