import requests
from autopatch.utils.secrets import get_secret

BASE_URL = "https://api.fivetran.com/v1"


def get_fivetran_client():
    api_key = get_secret("fivetran-api-key")
    api_secret = get_secret("fivetran-api-secret")
    return (api_key, api_secret)


def list_connectors() -> list:
    """
    Lists ALL Fivetran connectors — no filtering by name.
    Works for any data source.
    """
    auth = get_fivetran_client()
    response = requests.get(f"{BASE_URL}/connectors", auth=auth)
    data = response.json()

    if data.get("code") != "Success":
        raise Exception(f"Fivetran API error: {data}")

    connectors = []
    for item in data["data"]["items"]:
        connectors.append({
            "id": item["id"],
            "schema": item["schema"],
            "service": item["service"],
            "status": item["status"]["sync_state"],
            "succeeded_at": item.get("succeeded_at"),
            "failed_at": item.get("failed_at"),
        })

    return connectors


def get_connector_schema(connector_id: str) -> dict:
    """
    Fetches the full schema of a connector.
    """
    auth = get_fivetran_client()
    response = requests.get(
        f"{BASE_URL}/connectors/{connector_id}/schemas",
        auth=auth
    )
    data = response.json()
    if data.get("code") != "Success":
        raise Exception(f"Schema fetch error: {data}")
    return data["data"]


def get_current_columns(connector_id: str) -> list:
    """
    Returns the current column names from a Fivetran connector schema.
    Dynamic — works for any connector.
    """
    schema_data = get_connector_schema(connector_id)
    columns = []
    for schema_name, schema_data in schema_data.get("schemas", {}).items():
        for table_name, table_data in schema_data.get("tables", {}).items():
            for col_name in table_data.get("columns", {}).keys():
                columns.append(col_name)
    return columns


def detect_schema_changes(connector_id: str, known_columns: list) -> dict:
    """
    Detects schema drift by comparing current schema
    against known columns from the dbt model.
    Works for ANY connector — no hardcoding.

    Args:
        connector_id: Fivetran connector ID
        known_columns: columns referenced in the dbt model (source of truth)
    """
    current_columns = get_current_columns(connector_id)

    known_set = set(known_columns)
    current_set = set(current_columns)

    removed = list(known_set - current_set)
    added = list(current_set - known_set)

    potentially_renamed = []
    if removed and added:
        for r in removed:
            for a in added:
                potentially_renamed.append({"from": r, "to": a})

    return {
        "connector_id": connector_id,
        "removed_columns": removed,
        "added_columns": added,
        "potentially_renamed": potentially_renamed,
        "drift_detected": len(removed) > 0 or len(added) > 0,
        "current_columns": current_columns,
    }


def trigger_resync(connector_id: str) -> dict:
    """Triggers a full resync of a connector."""
    auth = get_fivetran_client()
    response = requests.post(
        f"{BASE_URL}/connectors/{connector_id}/resync",
        auth=auth
    )
    return response.json()
