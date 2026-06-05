import requests
from autopatch.utils.secrets import get_secret

# Fivetran API base URL
BASE_URL = "https://api.fivetran.com/v1"


def get_fivetran_client():
    """
    Returns auth tuple for Fivetran API requests.
    Fetches keys fresh from Secret Manager each time.
    """
    api_key = get_secret("fivetran-api-key")
    api_secret = get_secret("fivetran-api-secret")
    return (api_key, api_secret)


def list_connectors() -> list:
    """
    Lists all Fivetran connectors in your account.
    The agent calls this first to get a full picture
    of all active data pipelines.
    
    Returns:
        List of connectors with id, schema, status, service name
    """
    auth = get_fivetran_client()
    response = requests.get(f"{BASE_URL}/connectors", auth=auth)
    data = response.json()

    if data.get("code") != "Success":
        raise Exception(f"Fivetran API error: {data}")

    connectors = []
    for item in data["data"]["items"]:
        connectors.append({
            "id":           item["id"],
            "schema":       item["schema"],
            "service":      item["service"],
            "status":       item["status"]["sync_state"],
            "succeeded_at": item.get("succeeded_at"),
            "failed_at":    item.get("failed_at"),
        })

    return connectors


def get_connector_schema(connector_id: str) -> dict:
    """
    Fetches the full schema of a specific connector.
    This is how AutoPatch sees the current column structure
    of your source data — what columns exist right now.
    
    Args:
        connector_id: The Fivetran connector ID
    
    Returns:
        Schema dict with tables and columns
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


def get_connector_details(connector_id: str) -> dict:
    """
    Gets full details of a specific connector including
    last sync time, error messages, and sync status.
    The agent uses this to understand WHY a connector
    failed, not just that it failed.
    
    Args:
        connector_id: The Fivetran connector ID
    
    Returns:
        Full connector details including any error messages
    """
    auth = get_fivetran_client()
    response = requests.get(
        f"{BASE_URL}/connectors/{connector_id}",
        auth=auth
    )
    data = response.json()

    if data.get("code") != "Success":
        raise Exception(f"Connector details error: {data}")

    return data["data"]


def trigger_resync(connector_id: str) -> dict:
    """
    Triggers a full resync of a connector.
    The agent calls this AFTER the GitLab fix MR is merged
    to pull in the corrected data immediately.
    
    Args:
        connector_id: The Fivetran connector ID
    
    Returns:
        API response confirming the resync was triggered
    """
    auth = get_fivetran_client()
    response = requests.post(
        f"{BASE_URL}/connectors/{connector_id}/resync",
        auth=auth
    )
    data = response.json()
    return data


def detect_schema_changes(connector_id: str, known_columns: list) -> dict:
    """
    Compares current schema against known expected columns
    and identifies what changed. This is the core drift
    detection function — it tells the agent exactly what
    broke and what the new column names are.
    
    Args:
        connector_id: The Fivetran connector ID
        known_columns: List of column names we expect to exist
    
    Returns:
        Dict with added, removed, and potentially_renamed columns
    """
    current_schema = get_connector_schema(connector_id)

    # Extract all current column names from the schema
    current_columns = []
    for table_name, table_data in current_schema.get("schemas", {}).items():
        for tbl, tbl_data in table_data.get("tables", {}).items():
            for col in tbl_data.get("columns", {}).keys():
                current_columns.append(col)

    known_set = set(known_columns)
    current_set = set(current_columns)

    removed = list(known_set - current_set)
    added = list(current_set - known_set)

    # If a column was removed AND one was added, it was likely renamed
    potentially_renamed = []
    if removed and added:
        for r in removed:
            for a in added:
                potentially_renamed.append({
                    "from": r,
                    "to":   a
                })

    return {
        "connector_id":       connector_id,
        "removed_columns":    removed,
        "added_columns":      added,
        "potentially_renamed": potentially_renamed,
        "drift_detected":     len(removed) > 0 or len(added) > 0
    }
