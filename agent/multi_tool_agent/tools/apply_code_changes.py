import json
from typing import List, Tuple
from pydantic import BaseModel

# Pydantic models for the structured output of the Coder LLM.
class CoderChange(BaseModel):
    is_new_file: bool
    file_path: str
    action: str = "replace"
    start_line: int | None = None
    end_line: int | None = None
    new_code: str

class CoderResponse(BaseModel):
    pr_description: str
    changes: List[CoderChange]

def apply_code_changes(code_changes_json: str, original_file_contents: List[Tuple[str, str]]) -> Tuple[str, List[Tuple[str, str]]]:
    """
    Applies the code changes from the Coder LLM to the original file contents.
    Returns a tuple of (pr_description, modified_file_contents).
    Applies changes from bottom up to avoid line shifting issues.
    """
    cleaned_coder_json = code_changes_json.strip().strip('```json').strip()
    
    if not cleaned_coder_json or cleaned_coder_json == "":
        return None, original_file_contents
    
    coder_data = json.loads(cleaned_coder_json)

    coder_response = CoderResponse(**coder_data)

    working_files = dict(original_file_contents)
    
    # Group changes by file
    file_to_changes = {}
    for change in coder_response.changes:
        file_to_changes.setdefault(change.file_path, []).append(change)

    for file_path, changes in file_to_changes.items():
        # Handle new files immediately
        new_file_changes = [c for c in changes if c.is_new_file]
        for change in new_file_changes:
            working_files[change.file_path] = change.new_code
        # Only apply non-new-file changes bottom-up
        mod_changes = [c for c in changes if not c.is_new_file]
        # Sort by start_line descending
        mod_changes.sort(key=lambda c: c.start_line if c.start_line is not None else -1, reverse=True)
        for change in mod_changes:
            if change.file_path not in working_files:
                print(f"Warning: Coder attempted to modify a file not provided by the analyst: {change.file_path}")
                continue
            original_content_lines = working_files[change.file_path].splitlines()
            start_index = change.start_line - 1 if change.start_line is not None else 0
            end_index = change.end_line if change.end_line is not None else 0
            if not (0 <= start_index < len(original_content_lines) and start_index < end_index <= len(original_content_lines)):
                print(f"Warning: Invalid line numbers ({change.start_line}-{change.end_line}) provided for {change.file_path}. Skipping change.")
                continue
            new_code_lines = change.new_code.splitlines()
            new_content_list = (
                original_content_lines[:start_index] +
                new_code_lines +
                original_content_lines[end_index:]
            )
            working_files[change.file_path] = "\n".join(new_content_list)
    
    return coder_response.pr_description, list(working_files.items())
