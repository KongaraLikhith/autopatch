from autopatch.agent.autopatch_agent import run_agent

if __name__ == "__main__":
    run_agent(
        "Check all my Fivetran pipelines for schema drift. "
        "If anything is broken, calculate the business impact "
        "and create a GitLab MR to fix it automatically."
    )
