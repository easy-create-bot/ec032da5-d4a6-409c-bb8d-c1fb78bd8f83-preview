from typing import List, Dict
import requests

GITHUB_API_BASE = "https://api.github.com"

class GitHubTreeRetrievalError(RuntimeError):
    """Raised when we fail to retrieve the tree for a repo."""

def get_repo_tree(owner: str, repo_name: str, branch: str, access_token: str) -> List[Dict]:
    """Return the full file tree for the given GitHub repository branch.

    Parameters are primitives (str) so the Google ADK LLM can auto-generate
    the function-call.
    """

    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/vnd.github+json"}
    #1) resolve the branch ref to get the commit object URL
    
    ref_url = f"{GITHUB_API_BASE}/repos/{owner}/{repo_name}/git/refs/heads/{branch}"

    ref_resp = requests.get(ref_url, headers=headers, timeout=30)
    if ref_resp.status_code != 200:
        raise GitHubTreeRetrievalError(f"Failed to fetch branch ref: {ref_resp.status_code} {ref_resp.text}")

    ref_json = ref_resp.json()
    if isinstance(ref_json, list):  # GitHub can return an array if wildcard used
        ref_json = ref_json[0]
    try:
        object_url = ref_json["object"]["url"]
    except KeyError as exc:
        raise GitHubTreeRetrievalError(f"Unexpected ref JSON structure: {ref_json}") from exc

    # 2) get the tree URL from the commit object
    obj_resp = requests.get(object_url, headers=headers, timeout=30)
    if obj_resp.status_code != 200:
        raise GitHubTreeRetrievalError(f"Failed to fetch commit object: {obj_resp.status_code} {obj_resp.text}")
    try:
        tree_url = obj_resp.json()["tree"]["url"]
    except KeyError as exc:
        raise GitHubTreeRetrievalError("Commit JSON missing tree URL") from exc

    # 3) fetch the full tree recursively
    tree_resp = requests.get(f"{tree_url}?recursive=1", headers=headers, timeout=60)
    
    if tree_resp.status_code != 200:
        raise GitHubTreeRetrievalError(f"Failed to fetch tree: {tree_resp.status_code} {tree_resp.text}")

    flat_items = tree_resp.json().get("tree", [])
    return build_tree_from_flat_list(flat_items)

def build_tree_from_flat_list(flat_items: List[Dict]) -> List[Dict]:
    ignored_folders = {'node_modules', '.git', 'dist', 'build', 'coverage'}
    root_nodes = {}  # Use a dictionary as a map

    for item in flat_items:
        path = item.get('path', '')
        if any(part in ignored_folders for part in path.split('/')):
            continue

        parts = path.split('/')
        current_level_nodes = root_nodes
        current_path = ""

        for i, part in enumerate(parts):
            current_path = f"{current_path}/{part}" if current_path else part
            
            if part not in current_level_nodes:
                is_last_part = (i == len(parts) - 1)
                node = {
                    'name': part,
                    'path': current_path,
                    'type': item['type'] if is_last_part else 'tree',
                    'sha': item['sha'],
                    'url': item['url'],
                }
                if not is_last_part:
                    node['children'] = []
                current_level_nodes[part] = node

            parent_node = current_level_nodes[part]
            if '_children_map' not in parent_node:
                # Convert children list to a map for efficient lookup
                children_map = {}
                if 'children' in parent_node:
                    for child in parent_node['children']:
                        children_map[child['name']] = child
                parent_node['_children_map'] = children_map

            current_level_nodes = parent_node['_children_map']
    
    def map_to_array(node_dict):
        """Recursively converts _children_map back to a children list."""
        final_list = []
        for node in node_dict.values():
            if '_children_map' in node:
                node['children'] = map_to_array(node['_children_map'])
                del node['_children_map']
            final_list.append(node)
        return final_list

    return map_to_array(root_nodes)

