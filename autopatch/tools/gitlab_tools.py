import gitlab
from autopatch.utils.secrets import get_secret


def get_gitlab_client():
    """
    Returns an authenticated GitLab client.
    """
    token = get_secret("gitlab-token")
    gl = gitlab.Gitlab("https://gitlab.com", private_token=token)
    gl.auth()
    return gl


def get_project():
    """
    Returns your autopatch-dbt GitLab project.
    This is where your dbt models live.
    """
    gl = get_gitlab_client()
    project_path = get_secret("gitlab-project-path")
    return gl.projects.get(project_path)


def read_file(file_path: str, branch: str = "main") -> str:
    """
    Reads a file from your GitLab repo.
    The agent uses this to read the current broken
    dbt model SQL before deciding how to fix it.

    Args:
        file_path: Path inside repo e.g. "models/revenue.sql"
        branch: Branch to read from, default "main"

    Returns:
        File contents as a string
    """
    project = get_project()
    file = project.files.get(file_path=file_path, ref=branch)
    return file.decode().decode("utf-8")


def list_files(folder: str = "models") -> list:
    """
    Lists all files in a folder of your repo.
    Agent uses this to discover all dbt models
    that might be affected by a schema change.

    Args:
        folder: Folder path to list e.g. "models"

    Returns:
        List of file paths
    """
    project = get_project()
    items = project.repository_tree(path=folder, recursive=True)
    return [item["path"] for item in items if item["type"] == "blob"]


def create_fix_branch(branch_name: str) -> str:
    """
    Creates a new branch in GitLab for the fix.
    We never commit directly to main — always
    through a proper branch and MR.

    Args:
        branch_name: Name for the fix branch

    Returns:
        The branch name that was created
    """
    project = get_project()
    project.branches.create({
        "branch": branch_name,
        "ref": "main"
    })
    print(f"✅ Created branch: {branch_name}")
    return branch_name


def commit_fix(
    branch_name: str,
    file_path: str,
    fixed_content: str,
    commit_message: str
) -> dict:
    """
    Commits the fixed SQL file to the fix branch.
    This is AutoPatch writing the actual code fix.

    Args:
        branch_name: The fix branch to commit to
        file_path: Path of the file to update
        fixed_content: The corrected SQL content
        commit_message: Descriptive commit message

    Returns:
        Commit details
    """
    project = get_project()
    data = {
        "branch": branch_name,
        "commit_message": commit_message,
        "actions": [
            {
                "action": "update",
                "file_path": file_path,
                "content": fixed_content,
            }
        ],
    }
    commit = project.commits.create(data)
    print(f"✅ Fix committed: {commit.id}")
    return {"commit_id": commit.id, "branch": branch_name}


def create_merge_request(
    branch_name: str,
    title: str,
    description: str
) -> dict:
    """
    Opens a Merge Request for the fix.
    This is the final AutoPatch action — a proper
    MR that a human can review and merge with one click.

    Args:
        branch_name: The fix branch
        title: MR title e.g. "Fix: schema drift in order_amount"
        description: Full explanation of what broke and why

    Returns:
        MR details including URL for the agent to report back
    """
    project = get_project()
    mr = project.mergerequests.create({
        "source_branch": branch_name,
        "target_branch": "main",
        "title": title,
        "description": description,
        "remove_source_branch": True,
    })
    print(f"✅ MR created: {mr.web_url}")
    return {
        "mr_id":  mr.iid,
        "title":  mr.title,
        "url":    mr.web_url,
        "status": mr.state,
    }
