import time
from autopatch.agent.autopatch_agent import run_agent

if __name__ == "__main__":
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = run_agent(
                "Check all my Fivetran pipelines for schema drift. "
                "If anything is broken, calculate the business impact "
                "and create a GitLab MR to fix it automatically."
            )
            break
        except Exception as e:
            if "429" in str(e) and attempt < max_retries - 1:
                wait = 60
                print(f"\n⏳ Rate limit hit. Waiting {wait}s before retry {attempt + 2}/{max_retries}...")
                time.sleep(wait)
            else:
                raise
