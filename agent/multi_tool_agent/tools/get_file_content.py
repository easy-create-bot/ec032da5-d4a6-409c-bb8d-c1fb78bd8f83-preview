import requests
import base64

GITHUB_API_BASE = "https://api.github.com"

class FileContentError(RuntimeError):
    """Custom exception for file content retrieval errors."""

def get_file_content(owner: str, repo_name: str, path: str, access_token: str) -> str:
    """
    Fetches and decodes the content of a file from a GitHub repository.
    Returns an error message if the file doesn't exist instead of raising an exception.
    """
    print(f"Getting file content for {owner}/{repo_name}/{path}")
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo_name}/contents/{path}"
    headers = {
        "Authorization": f"token {access_token}",
        "Accept": "application/vnd.github+json"
    }
    
    response = requests.get(url, headers=headers, timeout=30)
    
    # Handle 404 specifically - file doesn't exist
    if response.status_code == 404:
        return f"ERROR: File '{path}' does not exist in the repository. Please check the repo tree first to see available files. If you're trying to create a new file, you don't need to read it - instead, look at similar existing files for patterns."
    
    # Handle other error codes
    if response.status_code != 200:
        return f"ERROR: Failed to fetch file content (HTTP {response.status_code}). Please verify the file path exists in the repo tree."

    data = response.json()
    
    if 'content' not in data:
        # Check if it's a directory
        if isinstance(data, list):
            return f"ERROR: '{path}' is a directory, not a file. Use get_repo_tree to see its contents."
        return f"ERROR: Unable to read content for '{path}'. This might be a directory or special file."
        
    encoded_content = data['content']
    
    try:
        decoded_bytes = base64.b64decode(encoded_content)
        decoded_content = decoded_bytes.decode('utf-8')
    except (TypeError, ValueError) as e:
        # Return error message instead of raising
        return f"ERROR: File '{path}' exists but couldn't be decoded as text. It might be a binary file."
    
    return decoded_content

