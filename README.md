# AutoPatch

> *It's 2am. Your board meeting is in 6 hours. Your revenue data is wrong. You're asleep. AutoPatch isn't.*

AutoPatch is an autonomous agent that sits between your data ingestion and your warehouse. When an upstream schema changes, it catches the drift, figures out the downstream impact, and opens a GitLab MR to fix your dbt models before the morning standup.

Built for the [Google Cloud Rapid Agent Hackathon 2026](https://rapid-agent.devpost.com/).

## The Stack
- **Agent Brain:** Google ADK + Gemini 1.5 Flash
- **Integration:** Fivetran MCP (Source), BigQuery (Warehouse), GitLab MCP (VCS)
- **Observability:** Arize Phoenix (LLM tracing)
- **Frontend:** Streamlit (v2 Dark Mode Command Center)
- **Package Management:** `uv`

## Getting Started

AutoPatch uses `uv` for package management because it's incredibly fast. If you don't have it installed, run `pip install uv` first.

```bash
git clone [https://github.com/KongaraLikhith/autopatch.git](https://github.com/KongaraLikhith/autopatch.git)
cd autopatch
uv venv
uv sync
```

### Environment Setup

You will need a few keys to get the agent talking to your infrastructure. Create a `.env` file in the root directory:

```env
GEMINI_API_KEY=your_gemini_key
PHOENIX_API_KEY=your_arize_phoenix_key
PHOENIX_COLLECTOR_ENDPOINT=[https://app.phoenix.arize.com/s/likhith0715](https://app.phoenix.arize.com/s/likhith0715)
FIVETRAN_API_KEY=your_fivetran_key
FIVETRAN_API_SECRET=your_fivetran_secret
GITLAB_TOKEN=your_gitlab_token
```
*(Note: For production deployments, pull these from GCP Secret Manager instead).*

### Running the App

```bash
uv run python app.py
```
The UI will spin up at `http://localhost:8501`. 

## How to use it
1. Check the dashboard to make sure the Fivetran and BigQuery layers are connected (the status LEDs should be green).
2. Hit **Initialize Agent Protocol** to kick off a pipeline scan.
3. The terminal in the UI will stream the agent's thought process in real-time. 
4. **Want to see the LLM's brain?** Click the "Live Traces" button to jump into Arize Phoenix and inspect the exact tool payloads, context windows, and token usage.
5. If the agent finds a break, review the incident report and follow the link to the generated GitLab MR.

## Notes
- Dependencies are strictly pinned in `uv.lock` to prevent weird environment conflicts.
- The UI is stateless. If the app is restarted, the local logs clear, but the trace history lives safely in Phoenix.