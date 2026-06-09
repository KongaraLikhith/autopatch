from google.cloud import bigquery

_client = None

def get_client():
    global _client
    if _client is None:
        _client = bigquery.Client(project="autopatch-498421")
    return _client


def get_all_datasets() -> list:
    """
    Returns all datasets in the project.
    Used to discover what Fivetran has synced dynamically.
    """
    datasets = list(get_client().list_datasets())
    return [d.dataset_id for d in datasets
            if not d.dataset_id.startswith("_")
            and "fivetran_metadata" not in d.dataset_id]


def get_all_tables(dataset_id: str) -> list:
    """
    Returns all tables in a dataset with their column schemas.
    """
    tables = []
    for table_ref in get_client().list_tables(dataset_id):
        table = get_client().get_table(table_ref)
        columns = [
            {"name": f.name, "type": f.field_type}
            for f in table.schema
            if not f.name.startswith("_")  # skip Fivetran system columns
        ]
        tables.append({
            "dataset": dataset_id,
            "table": table_ref.table_id,
            "full_ref": f"autopatch-498421.{dataset_id}.{table_ref.table_id}",
            "columns": columns,
            "column_names": [c["name"] for c in columns]
        })
    return tables


def get_table_schema(table_ref: str) -> list:
    """
    Fetches schema for a specific table.
    """
    table = get_client().get_table(table_ref)
    return [
        {"name": f.name, "type": f.field_type}
        for f in table.schema
        if not f.name.startswith("_")
    ]


def run_query(sql: str) -> list:
    """
    Runs a BigQuery SQL query and returns results.
    """
    query_job = get_client().query(sql)
    return [dict(row) for row in query_job.result()]


def calculate_business_impact(table_ref: str, broken_column: str) -> dict:
    """
    Calculates business impact of a broken column dynamically.
    Works for any table, not just orders.
    """
    print(f"💰 Calculating business impact for broken column: {broken_column}")

    count_sql = f"SELECT COUNT(*) as affected_rows FROM `{table_ref}`"
    try:
        count_result = run_query(count_sql)
        affected_rows = count_result[0]["affected_rows"] if count_result else 0
    except Exception:
        affected_rows = 0

    # Try to calculate revenue impact if an amount column exists
    revenue_sql = f"""
        SELECT COUNT(*) as row_count
        FROM `{table_ref}`
    """
    try:
        result = run_query(revenue_sql)
        row_count = result[0]["row_count"] if result else 0
    except Exception:
        row_count = affected_rows

    severity = "CRITICAL" if affected_rows > 100 else "HIGH" if affected_rows > 10 else "MEDIUM"

    impact = {
        "broken_column": broken_column,
        "table": table_ref,
        "affected_rows": affected_rows,
        "severity": severity,
        "summary": (
            f"{affected_rows} rows affected in `{table_ref}`. "
            f"Column `{broken_column}` no longer exists in source. "
            f"Downstream models referencing this column are broken."
        )
    }

    print(f"🚨 Impact: {impact['summary']}")
    return impact


def verify_tables_exist() -> dict:
    """
    Dynamically checks all synced tables exist.
    """
    results = {}
    try:
        datasets = get_all_datasets()
        for dataset in datasets:
            tables = get_all_tables(dataset)
            for t in tables:
                results[t["full_ref"]] = "✅ exists"
    except Exception as e:
        results["error"] = str(e)
    return results
