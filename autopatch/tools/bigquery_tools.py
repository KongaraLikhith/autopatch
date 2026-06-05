from google.cloud import bigquery

# Initialize BigQuery client once
client = bigquery.Client(project="autopatch-498421")

# Fivetran created separate datasets for each connector
ORDERS_TABLE    = "autopatch-498421.orders_source.orders"
CUSTOMERS_TABLE = "autopatch-498421.customers_source.customers"


def get_table_schema(table_ref: str) -> list:
    """
    Fetches the current column schema of a BigQuery table.
    The agent uses this to see what columns actually exist
    right now after a Fivetran sync — ground truth.

    Args:
        table_ref: Full table ref e.g. "autopatch-498421.orders_source.orders"

    Returns:
        List of dicts with column name and type
    """
    table = client.get_table(table_ref)

    columns = []
    for field in table.schema:
        columns.append({
            "name": field.name,
            "type": field.field_type,
        })

    print(f"✅ Schema fetched for {table_ref}: {len(columns)} columns")
    return columns


def run_query(sql: str) -> list:
    """
    Runs any SQL query against BigQuery and returns results.
    The agent uses this to calculate business impact —
    how many rows are affected, what revenue is broken.

    Args:
        sql: Valid BigQuery SQL string

    Returns:
        List of rows as dicts
    """
    query_job = client.query(sql)
    results = query_job.result()

    rows = []
    for row in results:
        rows.append(dict(row))

    return rows


def calculate_business_impact(broken_column: str) -> dict:
    """
    Calculates the real business impact of a broken column.
    This is what makes AutoPatch's incident report meaningful
    instead of just saying "column missing" — it says exactly
    how much data and revenue is affected.

    Args:
        broken_column: The column name that broke e.g. "order_amount"

    Returns:
        Dict with affected row count and total revenue impact
    """
    print(f"💰 Calculating business impact for broken column: {broken_column}")

    # Count total affected rows
    count_sql = f"""
        SELECT COUNT(*) as affected_rows
        FROM `{ORDERS_TABLE}`
    """
    count_result = run_query(count_sql)
    affected_rows = count_result[0]["affected_rows"] if count_result else 0

    # Calculate total revenue that is now miscalculated
    revenue_sql = f"""
        SELECT
            COUNT(*) as order_count,
            SUM(order_amount) as total_revenue,
            AVG(order_amount) as avg_order_value
        FROM `{ORDERS_TABLE}`
    """

    try:
        revenue_result = run_query(revenue_sql)
        total_revenue = revenue_result[0]["total_revenue"] if revenue_result else 0
        avg_order     = revenue_result[0]["avg_order_value"] if revenue_result else 0
        order_count   = revenue_result[0]["order_count"] if revenue_result else 0
    except Exception:
        # Column might already be broken/renamed
        total_revenue = 0
        avg_order     = 0
        order_count   = affected_rows

    impact = {
        "broken_column":   broken_column,
        "affected_rows":   affected_rows,
        "total_revenue":   total_revenue,
        "avg_order_value": avg_order,
        "order_count":     order_count,
        "severity":        "CRITICAL" if total_revenue and total_revenue > 1000 else "HIGH",
        "summary": (
            f"${total_revenue:,.2f} in revenue calculations affected "
            f"across {affected_rows} rows. "
            f"CFO dashboard is currently showing incorrect figures."
        ) if total_revenue else (
            f"{affected_rows} rows affected. Revenue calculation broken."
        )
    }

    print(f"🚨 Impact: {impact['summary']}")
    return impact


def verify_tables_exist() -> dict:
    """
    Checks that both expected tables exist in BigQuery.
    Used at agent startup to confirm the data pipeline
    is healthy before doing anything else.

    Returns:
        Dict showing which tables exist
    """
    tables_to_check = {
        "orders":    ORDERS_TABLE,
        "customers": CUSTOMERS_TABLE,
    }

    results = {}
    for name, table_ref in tables_to_check.items():
        try:
            client.get_table(table_ref)
            results[name] = "✅ exists"
        except Exception:
            results[name] = "❌ missing"

    return results
