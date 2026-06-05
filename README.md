# AutoPatch 🔧

> *It's 2am. Your board meeting is in 6 hours. Your revenue data is wrong. You're asleep. AutoPatch isn't.*

AutoPatch is an autonomous AI agent that monitors data pipelines, detects schema drift, and automatically creates fix pull requests — before anyone notices the dashboard is broken.

## What it does
- 🔍 **Detects** schema changes across Fivetran connectors in real time
- 🧠 **Diagnoses** downstream impact on dbt models using Gemini
- 🛠️ **Fixes** broken models by auto-creating a GitLab Merge Request
- 🔁 **Learns** from past decisions using Arize Phoenix trace memory

## Tech Stack
| Layer | Technology |
|---|---|
| AI Agent | Google ADK + Gemini 1.5 Flash |
| Data Pipeline | Fivetran MCP |
| Code Automation | GitLab MCP |
| Observability | Arize Phoenix MCP |
| Data Warehouse | BigQuery |
| Deployment | Cloud Run (GCP) |

## Built for
[Google Cloud Rapid Agent Hackathon 2026](https://rapid-agent.devpost.com/)

## Setup
See [docs/setup.md](docs/setup.md) for full setup instructions.
