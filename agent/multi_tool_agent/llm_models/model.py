from parse_file_str import parse_file_str
from pydantic import BaseModel
from typing import List, Tuple

class AgentResponse(BaseModel):
    plan: str
    file_contents: List[Tuple[str, str]]

class Model:
    def __init__(self, name: str):
        self.name = name
    
    def get_fix_prompt(self, user_prompt: str, analyst_response: AgentResponse) -> str:
        coder_prompt_parts = [
            "You are an expert software engineer. Your task is to implement the following plan by modifying the provided files.",
            f"\nUser's Original Request: {user_prompt}",
            f"\nAnalyst's Issue or Plan: {analyst_response.plan}",
            "\n---",
            "**Important Style Guide:**",
            "When implementing the changes, you must carefully analyze the existing code in the provided files.",
            "1.  **Styling:** Your generated code *must* match the styling conventions of the existing file (e.g., Tailwind CSS, standard CSS classes, inline styles). Do not introduce a new styling methodology.",
            "2.  **Libraries:** You may introduce new, small libraries if they are necessary to implement the requested feature. However, you must not introduce new core frameworks (e.g., do not add Vue if the project uses React).",
            "3.  **Conventions:** Match the existing variable naming conventions and general code structure.",
            "4.  **Syntax and Placement:** Ensure that your code is syntactically correct and placed correctly within the existing code. Pay close attention to surrounding elements, like HTML tags and JSX elements, to avoid breaking the structure. For example, ensure that elements like `</div>` are not misplaced.",
            "\n---",
            "Here are the parsed AST structures for each file showing all function, class, and variable declarations:",
            "**Note:** You are receiving structured AST data (not raw file content) that includes:",
            "- Function declarations, arrow functions, and method definitions",
            "- Class declarations and variable declarations", 
            "- JSX elements (for React components)",
            "- Each declaration includes: type, name, start_line, end_line, and the actual code",
            "- Line numbers are accurate and can be used for precise modifications"

            "**IMPORTANT:**",
            "Make sure your code changes are only related to the plan and the files provided. Do not change anything else."
            "Do not change any imports, exports, or any other code that is not directly related to the user's request. I.E. default exports, etc"
            "You must only return the JSON object, no other text, explanation, or markdown formatting."
            "Double check the syntax of the code changes provided before returning the JSON object."
            "Do not return changes that contain syntax errors check parentheses, brackets, tags, etc."
        ]

        # Parse the files
        for file_path, file_content in analyst_response.file_contents:
            declarations = parse_file_str(file_content, file_path.split(".")[-1])
            coder_prompt_parts.append(f"\nFile: `{file_path}` (AST Declarations):\n```json\n{declarations}\n```")

        coder_prompt_parts.append("""
        ---
        Your task is to generate the specific code changes required to implement the plan. This may involve modifying existing files or creating new ones.

        **Your final and only output must be a single, raw JSON object.** Do not include any other text, explanation, or markdown formatting. The JSON object must conform to the following structure:
        {
          "pr_description": "A brief, professional sentence describing what this PR does (like an engineer would write)",
          "changes": [
            // List of change objects
          ]
        }

        **For modifying an existing file, use this structure for each change object:**

        **To REPLACE existing lines:**
        {
        "is_new_file": false,
        "file_path": "path/to/your/file.js",
        "action": "replace",
        "start_line": 42,
        "end_line": 45,
        "new_code": "The new lines of code to replace lines 42-45..."
        }

        **To INSERT new lines after a specific line:**
        {
        "is_new_file": false,
        "file_path": "path/to/your/file.js", 
        "action": "replace",
        "start_line": 46,
        "end_line": 46,
        "new_code": "The new lines to insert after line 45..."
        }

        **CRITICAL: start_line must ALWAYS be <= end_line. For insertions, use the same line number for both.**

        **For creating a new file, use this structure:**
        {
        "is_new_file": true,
        "file_path": "path/to/new/file.js",
        "new_code": "The entire content of the new file..."
        }

        Example output format:
        {
        "pr_description": "Add user authentication middleware to protect dashboard routes",
        "changes": [
            {
            "is_new_file": false,
            "file_path": "src/middleware/auth.js",
            "action": "replace",
            "start_line": 10,
            "end_line": 15,
            "new_code": "// updated code here"
            }
        ]
        }
        """)
        return "\n".join(coder_prompt_parts)

        
    def generate_content(self,user_prompt: str) -> str:
        pass