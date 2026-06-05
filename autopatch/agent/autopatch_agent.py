import asyncio
import os
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
    get_table_schema,
    calculate_business_impact,
)
from autopatch.utils.secrets import get_secret
from autopatch.utils.phoenix_tracer import setup_phoenix_tracing

EXPECTED_ORDER_COLUMNS = [
    "order_id",
    "customer_id",
    "product_name",
    "order_amount",
    "order_date",
]

DBT_MODEL_PATH = "models/revenue.sql"


def detect_drift_tool() -> dict:
    """
    Tool 1: Checks all Fivetran connectors for schema drift.
    Agent calls this first to understand what changed.
    """
    print("\n🔍 [Tool: detect_drift] Scanning connectors for schema drift...")

    connectors = list_connectors()
    drift_results = []

    for connector in connectors:
        if "fivetran_log" in connector["service"]:
            continue
        if "orders" in connector["schema"]:
            drift = detect_schema_changes(
                connector["id"],
                EXPECTED_ORDER_COLUMNS
            )
            drift["connector_name"] = connector["schema"]
            drift_results.append(drift)

    any_drift = any(d["drift_detected"] for d in drift_results)

    result = {
        "drift_detected": any_drift,
        "connectors_checked": len(drift_results),
        "drift_details": drift_results,
        "timestamp": datetime.utcnow().isoformat(),
    }

    print(f"   Drift detected: {any_drift}")
    return result


def calculate_impact_tool(broken_column: str) -> dict:
    """
    Tool 2: Calculates the business impact of a broken column.
    Agent calls this to quantify severity in dollars and rows.
    """
    print(f"\n💰 [Tool: calculate_impact] Assessing impact of: {broken_column}")
    return calculate_business_impact(broken_column)


def read_dbt_model_tool() -> dict:
    """
    Tool 3: Reads the current broken dbt model from GitLab.
    Agent calls this to understand exactly what SQL needs fixing.
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
    Tool 4: Creates a GitLab MR with the fixed dbt model.
    Agent calls this as the final action after diagnosing the fix.
    """
    print(f"\n🛠️  [Tool: create_fix_mr] Creating fix MR...")

    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    branch_name = f"fix/schema-drift-{old_column}-{timestamp}"

    create_fix_branch(branch_name)

    commit_message = (
        f"fix: update {old_column} to {new_column} in revenue model\n\n"
        f"AutoPatch detected schema drift at {timestamp}.\n"
        f"Column '{old_column}' was renamed to '{new_column}' in source.\n"
        f"Updated revenue.sql to use new column name."
    )
    commit_fix(branch_name, DBT_MODEL_PATH, fixed_sql, commit_message)

    mr_description = (
        f"## 🤖 AutoPatch — Automated Schema Drift Fix\n\n"
        f"### What happened\n"
        f"Column `{old_column}` was renamed to `{new_column}` "
        f"in the upstream Fivetran source.\n\n"
        f"### What broke\n"
        f"`revenue.sql` referenced `{old_column}` which no longer exists, "
        f"breaking the CFO dashboard.\n\n"
        f"### What this MR fixes\n"
        f"Updated `revenue.sql` to use `{new_column}` instead of `{old_column}`.\n\n"
        f"### Detected by\n"
        f"AutoPatch AI Agent — {timestamp}\n"
        f"Powered by Google ADK + Gemini + Fivetran MCP + Arize Phoenix"
    )

    mr = create_merge_request(
        branch_name,
        title=f"fix: schema drift — {old_column} renamed to {new_column}",
        description=mr_description,
    )

    return mr


def get_bigquery_schema_tool() -> dict:
    """
    Tool 5: Gets current BigQuery table schema as ground truth.
    Agent uses this to confirm what columns actually exist now.
    """
    print("\n📊 [Tool: get_bq_schema] Fetching current BigQuery schema...")
    cols = get_table_schema("autopatch-498421.orders_source.orders")
    return {
        "table": "orders_source.orders",
        "columns": cols,
    }


async def run_agent_async(user_message: str) -> str:
    """
    Async agent runner — sets API key, builds agent, runs it.
    """
    # Set Gemini API key from Secret Manager as environment variable
    # Google ADK picks it up automatically from here
    os.environ["GOOGLE_API_KEY"] = get_secret("gemini-api-key")

    # Set up Phoenix tracing
    setup_phoenix_tracing("autopatch")

    agent = Agent(
        name="AutoPatch",
        model="gemini-3-flash-preview",
        description=(
            "AutoPatch is an autonomous data pipeline monitoring agent. "
            "It detects schema drift in Fivetran connectors, calculates "
            "business impact, and automatically creates GitLab MRs to fix "
            "broken dbt models."
        ),
        instruction="""
You are AutoPatch, an autonomous AI agent for data pipeline reliability.

Your job is to detect schema drift, understand its business impact,
and fix broken dbt models by creating GitLab Merge Requests.

When a user reports a broken dashboard or asks you to check pipelines:

STEP 1 — DETECT
Call detect_drift_tool to scan all Fivetran connectors.
Report what schema changes were found.

STEP 2 — ASSESS IMPACT
If drift is detected, call calculate_impact_tool with the broken column name.
Calculate exactly how much revenue and how many rows are affected.
Always express impact in dollars.

STEP 3 — READ THE BROKEN MODEL
Call read_dbt_model_tool to see the current SQL.
Identify exactly which line references the broken column.

STEP 4 — FIX IT
Generate the corrected SQL by replacing the old column name with the new one.
Call create_fix_mr_tool with the old column, new column, and fixed SQL.
Report the MR URL so the user can review and merge with one click.

STEP 5 — INCIDENT REPORT
Always end with a clear incident report containing:
- What broke (column name and table)
- Business impact ($ amount and row count)
- Severity (CRITICAL/HIGH/MEDIUM)
- What was fixed (the MR link)
- Time to detect and fix

Be direct, confident, and professional. You are the on-call data engineer
who never sleeps. Your job is to make sure the CFO dashboard is always right.
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
        # ADK events have content not response
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
    """
    Synchronous wrapper around the async agent runner.
    """
    return asyncio.run(run_agent_async(user_message))
