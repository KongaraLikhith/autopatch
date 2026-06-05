from google.cloud import secretmanager

# Initialize the Secret Manager client once
client = secretmanager.SecretManagerServiceClient()

# Your GCP project ID
PROJECT_ID = "autopatch-498421"

def get_secret(secret_name: str) -> str:
    """
    Fetches a secret value from GCP Secret Manager.
    
    Args:
        secret_name: The name of the secret (e.g. "fivetran-api-key")
    
    Returns:
        The secret value as a plain string
    """
    name = f"projects/{PROJECT_ID}/secrets/{secret_name}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")


# Pre-load all secrets once at startup so we don't call Secret Manager
# repeatedly during agent execution
def load_all_secrets() -> dict:
    """
    Loads all AutoPatch secrets in one go.
    Returns a dictionary with all keys.
    """
    print("Loading secrets from GCP Secret Manager...")
    
    secrets = {
        "fivetran_api_key":      get_secret("fivetran-api-key"),
        "fivetran_api_secret":   get_secret("fivetran-api-secret"),
        "gitlab_token":          get_secret("gitlab-token"),
        "gitlab_username":       get_secret("gitlab-username"),
        "gitlab_project_path":   get_secret("gitlab-project-path"),
        "arize_phoenix_api_key": get_secret("arize-phoenix-api-key"),
    }
    
    print(f"✅ All {len(secrets)} secrets loaded successfully")
    return secrets
