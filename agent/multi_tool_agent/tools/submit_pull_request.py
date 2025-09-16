import requests
import uuid
from models import Repo

def submit_pull_request(repo: Repo, access_token: str, new_file_contents: dict, pr_description: str):
    branch_name = repo.default_branch

    # Get latest commit SHA of the main branch
    branch_resp = requests.get(
        f"https://api.github.com/repos/{repo.owner.login}/{repo.name}/git/ref/heads/{branch_name}",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    if branch_resp.status_code != 200:
        raise Exception(f"Failed to get branch: {branch_resp.status_code} {branch_resp.text}")
    commit_sha = branch_resp.json()['object']['sha']

    # Create a new branch
    branch_name = f"ticketAgent-{uuid.uuid4()}"
    create_branch_resp = requests.post(
        f"https://api.github.com/repos/{repo.owner.login}/{repo.name}/git/refs",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "ref": f"refs/heads/{branch_name}",
            "sha": commit_sha
        }
    )
    if create_branch_resp.status_code != 201:
        raise Exception(f"Failed to create branch: {create_branch_resp.status_code} {create_branch_resp.text}")

    # Create blobs from the new file contents
    blobs = {}
    for path, content in new_file_contents:
        blob_resp = requests.post(
            f"https://api.github.com/repos/{repo.owner.login}/{repo.name}/git/blobs",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "content": content,
                "encoding": "utf-8"
            }
        )
        if blob_resp.status_code != 201:
            raise Exception(f"Failed to create blob: {blob_resp.status_code} {blob_resp.text}")
        blobs[path] = blob_resp.json()["sha"]

    # Get base tree SHA
    base_tree_resp = requests.get(
        f"https://api.github.com/repos/{repo.owner.login}/{repo.name}/git/commits/{commit_sha}",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    if base_tree_resp.status_code != 200:
        raise Exception(f"Failed to get base tree: {base_tree_resp.status_code} {base_tree_resp.text}")
    base_tree_sha = base_tree_resp.json()["tree"]["sha"]

    # Create a tree from the blobs
    tree_items = [
        {
            "path": path,
            "mode": "100644",
            "type": "blob",
            "sha": blob_sha
        }
        for path, blob_sha in blobs.items()
    ]

    tree_resp = requests.post(
        f"https://api.github.com/repos/{repo.owner.login}/{repo.name}/git/trees",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "base_tree": base_tree_sha,
            "tree": tree_items
        }
    )
    if tree_resp.status_code != 201:
        raise Exception(f"Failed to create tree: {tree_resp.status_code} {tree_resp.text}")
    tree_sha = tree_resp.json()["sha"]

    # Create a commit
    commit_resp = requests.post(
        f"https://api.github.com/repos/{repo.owner.login}/{repo.name}/git/commits",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "message": "Automated commit from agent",
            "tree": tree_sha,
            "parents": [commit_sha]
        }
    )
    if commit_resp.status_code != 201:
        raise Exception(f"Failed to create commit: {commit_resp.status_code} {commit_resp.text}")
    new_commit_sha = commit_resp.json()["sha"]

    # Update the reference to point to new commit
    update_ref_resp = requests.patch(
        f"https://api.github.com/repos/{repo.owner.login}/{repo.name}/git/refs/heads/{branch_name}",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"sha": new_commit_sha}
    )
    if update_ref_resp.status_code != 200:
        raise Exception(f"Failed to update ref: {update_ref_resp.status_code} {update_ref_resp.text}")

    # Create a pull request
    pr_resp = requests.post(
        f"https://api.github.com/repos/{repo.owner.login}/{repo.name}/pulls",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "title": pr_description,
            "head": branch_name,
            "base": repo.default_branch,
            "body": "This PR was created automatically by the agent. Please review and merge."
        }
    )
    if pr_resp.status_code != 201:
        raise Exception(f"Failed to create pull request: {pr_resp.status_code} {pr_resp.text}")

    pr_url = pr_resp.json()["html_url"]

    return pr_url