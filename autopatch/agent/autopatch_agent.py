import asyncio
import os
import re
import time
from datetime import datetime

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from autopatch.tools.fivetran_tools import (
    list_connectors,
    detect_schema_changes,
)
from autopatch.tools.gitlab_tools import (
    read_file,
    create_fix_branch,
    commit_fix,
    create_merge_request,
)
from autopatch.tools.bigquery_tools import (
    get_all_datasets,
    get_all_tables,
    calculate_business_impact,
)
from autopatch.utils.phoenix_tracer import setup_phoenix_tracing
from autopatch.utils.secrets import get_secret

# Only hardcoded value — the dbt model path in GitLab
# Everything else is discovered dynamically
DBT_MODEL_PATH = "models/revenue.sql"


def detect_drift_tool() -> dict:
    """
    Tool 1: Scans ALL Fivetran connectors for schema drift.
    Dynamically reads the dbt model to know what columns are expected.
    No hardcoded column lists — works for any data source.
    """
    print("\n🔍 [Tool: detect_drift] Scanning ALL connectors for schema drift...")

    # Read dbt model to extract expected column names dynamically
    dbt_content = read_file(DBT_MODEL_PATH)

    # Extract column references from SQL — patterns like o.column_name
    col_refs = re.findall(r'[a-zA-Z]\\.([a-zA-Z_][a-zA-Z0-9_]*)', dbt_content)
    # Also catch standalone column names in SELECT
    select_cols = re.findall(r'(?:SELECT|,)\s+([a-zA-Z_][a-zA-Z0-9_]*)', dbt_content)
    expected_columns = list(set(col_refs + select_cols))

    # Filter out SQL keywords
    sql_keywords = {"this", "ref", "source", "config", "model", 
        "select", "from", "join", "where", "on", "as", "and", "or",
        "not", "in", "is", "null", "order", "by", "group", "having",
        "limit", "distinct", "case", "when", "then", "else", "end",
        "inner", "left", "right", "outer", "cross", "using", "with"
    }
    expected_columns = [c for c in expected_columns
                        if c.lower() not in sql_keywords and len(c) > 2]

    print(f"   Columns expected by dbt model: {expected_columns}")

    # Check ALL connectors dynamically
    connectors = list_connectors()
    drift_results = []

    for connector in connectors:
        if "fivetran_log" in connector["service"]:
            continue

        drift = detect_schema_changes(connector["id"], expected_columns)
        drift["connector_name"] = connector["schema"]
        drift["service"] = connector["service"]
        drift_results.append(drift)

    any_drift = any(d["drift_detected"] for d in drift_results)

    # Extract renamed column pairs
    renames = []
    for d in drift_results:
        for r in d.get("potentially_renamed", []):
            renames.append(r)

    result = {
        "drift_detected": any_drift,
        "connectors_checked": len(drift_results),
        "drift_details": drift_results,
        "column_renames": renames,
        "expected_columns": expected_columns,
        "timestamp": datetime.utcnow().isoformat(),
    }

    print(f"   Connectors checked: {len(drift_results)}")
    print(f"   Drift detected: {any_drift}")
    if renames:
        for r in renames:
            print(f"   Renamed: {r['from']} → {r['to']}")

    return result


def calculate_impact_tool(broken_column: str) -> dict:
    """
    Tool 2: Calculates business impact of a broken column.
    Dynamically finds the affected table in BigQuery.
    Works for any table — not hardcoded.
    """
    print(f"\n💰 [Tool: calculate_impact] Assessing impact of: {broken_column}")

    # Dynamically find which BigQuery table actually has this column
    try:
        datasets = get_all_datasets()
        for dataset in datasets:
            tables = get_all_tables(dataset)
            for table in tables:
                if broken_column in table["column_names"]:
                    return calculate_business_impact(table["full_ref"], broken_column)
        # Column not found (it was renamed) — use first non-customer table
        for dataset in datasets:
            tables = get_all_tables(dataset)
            for table in tables:
                if "order" in table["table"].lower():
                    return calculate_business_impact(table["full_ref"], broken_column)
    except Exception as e:
        print(f"   Could not auto-discover table: {e}")

    # Fallback
    return {
        "broken_column": broken_column,
        "affected_rows": 0,
        "severity": "HIGH",
        "summary": f"Column `{broken_column}` no longer exists in source data."
    }


def read_dbt_model_tool() -> dict:
    """
    Tool 3: Reads the current dbt model from GitLab.
    Returns the SQL content so the agent can see what needs fixing.
    """
    print(f"\n📄 [Tool: read_dbt_model] Reading {DBT_MODEL_PATH} from GitLab...")
    content = read_file(DBT_MODEL_PATH)
    return {
        "file_path": DBT_MODEL_PATH,
        "content": content,
    }


def create_fix_mr_tool(
    old_column: str,
    new_column: str,
    fixed_sql: str
) -> dict:
    """
    Tool 4: Creates a GitLab MR with the corrected dbt model.
    The agent calls this after generating the fix.

    Args:
        old_column: column name that broke e.g. "order_amount"
        new_column: what it was renamed to e.g. "quantity"
        fixed_sql: the corrected SQL with new column name
    """
    print(f"\n🛠️  [Tool: create_fix_mr] Creating fix MR...")

    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    branch_name = f"fix/schema-drift-{old_column}-{timestamp}"

    create_fix_branch(branch_name)

    commit_message = (
        f"fix: update {old_column} to {new_column} in dbt model\n\n"
        f"AutoPatch detected schema drift at {timestamp}.\n"
        f"Column '{old_column}' was renamed to '{new_column}' in source.\n"
        f"Updated {DBT_MODEL_PATH} to use new column name."
    )
    commit_fix(branch_name, DBT_MODEL_PATH, fixed_sql, commit_message)

    mr_description = (
        f"## 🤖 AutoPatch — Automated Schema Drift Fix\n\n"
        f"### What happened\n"
        f"Column `{old_column}` was renamed to `{new_column}` "
        f"in the upstream Fivetran source.\n\n"
        f"### What broke\n"
        f"`{DBT_MODEL_PATH}` referenced `{old_column}` "
        f"which no longer exists, breaking downstream dashboards.\n\n"
        f"### What this MR fixes\n"
        f"Updated `{DBT_MODEL_PATH}` to use `{new_column}` "
        f"instead of `{old_column}`.\n\n"
        f"### Detected by\n"
        f"AutoPatch AI Agent — {timestamp}\n"
        f"Powered by Google ADK + Gemini + Fivetran + GitLab + Arize Phoenix"
    )

    mr = create_merge_request(
        branch_name,
        title=f"fix: schema drift — {old_column} renamed to {new_column}",
        description=mr_description,
    )

    return mr


def get_bigquery_schema_tool() -> dict:
    """
    Tool 5: Dynamically discovers ALL BigQuery tables and their schemas.
    No hardcoded table names — works for any Fivetran destination.
    """
    print("\n📊 [Tool: get_bq_schema] Discovering all BigQuery tables...")

    try:
        datasets = get_all_datasets()
        all_tables = []
        for dataset in datasets:
            tables = get_all_tables(dataset)
            all_tables.extend(tables)

        print(f"   Found {len(all_tables)} tables across {len(datasets)} datasets")
        return {
            "datasets": datasets,
            "tables": all_tables,
            "total_tables": len(all_tables),
        }
    except Exception as e:
        return {"error": str(e)}


async def run_agent_async(user_message: str) -> str:
    """Async agent runner — fully dynamic, no hardcoding."""
    os.environ["GOOGLE_API_KEY"] = get_secret("gemini-api-key")

    setup_phoenix_tracing("autopatch")

    agent = Agent(
        name="AutoPatch",
        model="gemini-3.5-flash",
        description=(
            "AutoPatch is an autonomous AI agent for data pipeline reliability. "
            "It detects schema drift across ALL Fivetran connectors, calculates "
            "business impact, and automatically creates GitLab MRs to fix "
            "broken dbt models. Works for any data source — not hardcoded."
        ),
        instruction="""
You are AutoPatch, an autonomous AI agent for data pipeline reliability.
You work across ANY data source — not just specific tables or columns.

STEP 1 — DETECT
Call detect_drift_tool. It dynamically reads the dbt model to find
expected columns, then checks ALL Fivetran connectors for drift.
The result includes column_renames with exact from/to pairs.

STEP 2 — ASSESS IMPACT
If drift detected, call calculate_impact_tool with the broken column name.
It will automatically find the affected BigQuery table.

STEP 3 — READ THE BROKEN MODEL
Call read_dbt_model_tool to see the current SQL.

STEP 4 — FIX IT
Use column_renames[0]["from"] and column_renames[0]["to"] from Step 1
as old_column and new_column. Generate fixed SQL by replacing all
occurrences of old_column with new_column.
Call create_fix_mr_tool with old_column, new_column, fixed_sql.

STEP 5 — INCIDENT REPORT
End with a structured incident report:
- What broke (column and connector)
- Business impact (rows affected, severity)
- Fix deployed (GitLab MR link)
- Time to detect and fix

Be direct and professional. You are the on-call data engineer who never sleeps.
""",
        tools=[
            detect_drift_tool,
            calculate_impact_tool,
            read_dbt_model_tool,
            create_fix_mr_tool,
            get_bigquery_schema_tool,
        ],
    )

    session_service = InMemorySessionService()
    runner = Runner(
        agent=agent,
        app_name="autopatch",
        session_service=session_service,
    )

    session = await session_service.create_session(
        app_name="autopatch",
        user_id="user_001",
    )

    print(f"\n{'='*60}")
    print(f"🤖 AutoPatch Agent Starting")
    print(f"{'='*60}")
    print(f"User: {user_message}")
    print(f"{'='*60}\n")

    content = types.Content(
        role="user",
        parts=[types.Part(text=user_message)]
    )

    full_response = ""
    async for event in runner.run_async(
        user_id="user_001",
        session_id=session.id,
        new_message=content,
    ):
        if hasattr(event, "content") and event.content:
            for part in event.content.parts:
                if hasattr(part, "text") and part.text:
                    full_response = part.text

    print(f"\n{'='*60}")
    print("🤖 AutoPatch Response:")
    print(f"{'='*60}")
    print(full_response)

    return full_response


def run_agent(user_message: str) -> str:
    """Synchronous wrapper around the async agent runner."""
    return asyncio.run(run_agent_async(user_message))
