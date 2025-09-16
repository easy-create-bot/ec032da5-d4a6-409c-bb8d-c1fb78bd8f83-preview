from tree_sitter_language_pack import get_parser
from tree_sitter import Node
from typing import Optional, List, Tuple

def verify_code_changes(new_file_contents: List[Tuple[str,str]]) -> tuple[bool, str]:
    for file_path, file_content in new_file_contents:
        is_valid, error_message = verify_changes(file_content, file_path.split(".")[-1])
        if not is_valid:
            return False, error_message
    return True, ""

def verify_changes(code: str, lang_name: str) -> tuple[bool, str]:
    parser = get_parser(lang_name)
    tree = parser.parse(code.encode('utf-8'))

    if not tree.root_node.has_error:
        return True, ""
    
    error_node = find_error_node(tree.root_node)
    return False, f"line {error_node.start_point[0]+1}:{error_node.start_point[1]+1}"

def find_error_node(node: Node) -> Optional[Node]:
    """Depth-first search for the left-most error node."""
    if node.has_error:
        # Recurse so we return the *deepest* offending node,
        # which gives a more precise line/col.
        for child in node.children:
            found = find_error_node(child)
            if found:
                return found
        return node
    return None
