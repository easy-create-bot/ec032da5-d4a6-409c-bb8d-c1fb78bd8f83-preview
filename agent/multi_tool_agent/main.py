from typing import List, Tuple, Any
import uuid
import functools
from dotenv import load_dotenv
from pydantic import BaseModel
from google.adk.agents import Agent, SequentialAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService, Session
from google.genai import types
from prompt import agent_instructions
from tools.get_repo_tree import get_repo_tree
from tools.get_file_content import get_file_content
from models import Repo, TreeNode
from tools.apply_code_changes import apply_code_changes
from fix import get_code_changes
from tools.verify_changes import verify_changes
from tools.submit_pull_request import submit_pull_request
from llm_models.gpt import GPT
from llm_models.gemini import Gemini
from llm_models.claude import Claude
from socket_client import sio
import json

load_dotenv()

LANG = {"js": "javascript", "jsx": "javascript", "ts": "typescript", "tsx": "tsx"}

session_service = InMemorySessionService()

class AgentResponse(BaseModel):
    plan: str
    file_contents: List[Tuple[str,str]]

class ImplementChangesTool:
    def __init__(self, model: Any, repo: Repo, access_token: str, user_prompt: str, socket_id: str):
        self._model = model
        self._repo = repo
        self._access_token = access_token
        self._user_prompt = user_prompt
        self._socket_id = socket_id

    @property
    def __name__(self):
        return "implement_changes"

    def __call__(self, plan: str, file_paths: List[str]) -> str:
        print(f"Model: {self._model}")
        file_contents = []
        for path in file_paths:
            try:
                content = get_file_content(
                    owner=self._repo.owner.login,
                    repo_name=self._repo.name,
                    path=path,
                    access_token=self._access_token
                )
                file_contents.append((path, content))
            except Exception as e:
                return f"Error reading file {path}: {e}"

        for attempt in range(3):
            raw_analyst_output = json.dumps({"plan": plan, "file_contents": file_contents})
            print(f"Implementation attempt {attempt + 1}...\n {raw_analyst_output}")
            
            code_changes_json, _ = get_code_changes(
                user_prompt=self._user_prompt,
                raw_analyst_output=raw_analyst_output,
                llm_model=self._model,
            )
            print(f"Code changes: {code_changes_json}")

            if not code_changes_json:
                plan = f"{plan}\n\nThe last attempt failed to generate any code changes. Please try again."
                continue

            pr_description, new_file_contents = apply_code_changes(
                code_changes_json=code_changes_json,
                original_file_contents=file_contents
            )

            print(f"Verifying")
            verification_passed = True
            error_messages = []
            for file_path, file_content in new_file_contents:
                is_valid, error_message = verify_changes(file_content, LANG[file_path.split(".")[-1]])
                if not is_valid:
                    verification_passed = False
                    print(f"Verification failed for {file_path} with error: {error_message}.")
                    error_messages.append(f"Verification failed for {file_path} with error: {error_message}.")
            
            if verification_passed:
                print("Verification successful. Submitting pull request.")
                pr_url = submit_pull_request(
                    repo=self._repo,
                    access_token=self._access_token,
                    new_file_contents=new_file_contents,
                    pr_description=pr_description
                )
                return pr_url
            else:
                plan = f"{plan}\n\nVerification failed with the following errors:\n" + "\n".join(error_messages) + "\nPlease fix them."
                file_contents = new_file_contents

        return "Failed to implement and verify the changes after 3 attempts."

async def send_message_to_socket(socket_id: str, function_name: str, message: str = None):
    if not socket_id:
        return
        
    if function_name == 'get_repo_tree':
        await sio.emit('agent_response', {
            'message': message or 'Analyzing repository file structure...'
        }, room=socket_id)
    elif function_name == 'get_file_content':
        await sio.emit('agent_response', {
            'message': message or 'Reading file contents...'
        }, room=socket_id)
    elif function_name == 'implement_changes':
        await sio.emit('agent_response', {
            'message': message or 'Generating code changes...'
        }, room=socket_id)
    else:
        raise ValueError(f"Invalid function name: {function_name}")

async def run_agent_with_prompt(
    user_prompt: str,
    repo: Repo,
    access_token: str,
    socket_id: str,
    session_id: str | None = None,
    llm_model_type: str | None = None,
    llm_model_name: str | None = None,
):
    """
    Runs the simple ADK agent with a given user prompt and manages the session.
    """

    model = None
    if llm_model_type == "gpt":
        model = GPT(llm_model_name)
    elif llm_model_type == "gemini":
        model = Gemini(llm_model_name)
    elif llm_model_type == "claude":
        model = Claude(llm_model_name)
    else:
        raise ValueError(f"Invalid LLM model type: {llm_model_type}")

    implement_changes_tool = ImplementChangesTool(
        model=model,
        repo=repo,
        access_token=access_token,
        user_prompt=user_prompt,
        socket_id=socket_id
    )
    
    root_agent = Agent(
        name="Software_Engineer_Agent",
        model="gemini-2.5-pro",
        description=(
            "An agent that can analyze a repository, plan and execute code changes, and submit a pull request."
        ),
        instruction="""You are an expert software engineer. Your goal is to translate a user's request into a concrete plan, execute it, and submit a pull request.

Your workflow is as follows:
1.  **Analyze the Request:** Carefully read the user's prompt to understand their specific goal.
2.  **Explore the Codebase:** Use the `get_repo_tree` and `get_file_content` tools to find and read only the files that are directly relevant to implementing the user's request. Verify that the file paths exist inside the repo tree before calling `get_file_content`.
3.  **Formulate the Plan:** Create a concise plan that is a direct translation of the user's request into engineering steps and identify the full paths of the files to be modified.
4.  **Execute the Plan:** Call the `implement_changes` tool. This tool will handle the rest of the process, including retries.

**Important:**
- When calling `get_file_content`, you must always make sure that the file path being passed in is a valid file path in the repo tree.
- When formulating the plan, do not change any imports, exports, or any other code that is not directly related to the user's request.

**When calling `implement_changes`, you must provide arguments matching this schema:**
- `plan` (string): Your concise, high-level plan.
- `file_paths` (list of strings): The full paths to the files that need to be modified.

Your final output must be the pull request URL returned by the `implement_changes` tool.
""",
        tools=[get_repo_tree, get_file_content, implement_changes_tool],
    )

    current_user_id = "test-user-001" 
    app_name = 'multi_tool_agent'

    if session_id is None:
        new_session_id = str(uuid.uuid4())
        session = await session_service.create_session(user_id=current_user_id, session_id=new_session_id, app_name=app_name)
        current_session_id = new_session_id
        print(f"Created new session: {current_session_id}")
    else:
        try:
            # Attempt to retrieve an existing session
            session = await session_service.get_session(user_id=current_user_id, session_id=session_id, app_name=app_name)
            current_session_id = session_id
            print(f"Resuming session: {current_session_id}")
        except Exception:
            # If the session_id doesn't exist (e.g., first run with a specified ID, or old session), create a new one.
            session = await session_service.create_session(user_id=current_user_id, session_id=session_id, app_name=app_name)
            current_session_id = session_id
            print(f"Session {session_id} not found, creating new one with this ID.")

    runner = Runner(
        agent=root_agent,
        session_service=session_service,
        app_name=app_name,
    )

    agent_responses = []
    pr_url = None

    owner_login = repo.owner["login"] if isinstance(repo.owner, dict) else repo.owner.login
    
    prompt_for_tool_call = (
        f"{user_prompt}\n"
        f"owner: {owner_login}\n"
        f"repo_name: {repo.name}\n"
        f"branch: {repo.default_branch}\n"
        f"access_token: {access_token}"
    )

    content = types.Content(role='user',parts=[types.Part(text=prompt_for_tool_call)])

    async for event in runner.run_async(
        user_id=current_user_id,
        session_id=current_session_id,
        new_message=content,
    ):
        if event.content and event.content.parts:
            if event.get_function_calls():
                for call in event.get_function_calls():
                    print(f"Function call: {call.name}")
                    await send_message_to_socket(socket_id, call.name)
            elif event.get_function_responses():
                for response in event.get_function_responses():
                    if response.name == 'implement_changes' and response.response and 'result' in response.response:
                        pr_url = response.response['result']
                        print(f"Pull Request URL: {pr_url}")
                        return pr_url, current_session_id
            if event.content.parts[0].text:
                agent_responses.append(event.content.parts[0].text)
    
    if pr_url is not None and pr_url != 'Failed to implement and verify the changes after 3 attempts.':
        return pr_url, current_session_id
    
    return None, current_session_id    

async def run_agent(
    user_prompt: str,
    repo: Repo,
    access_token: str,
    socket_id: str,
    session_id: str | None = None,
    llm_model_type: str | None = None,
    llm_model_name: str | None = None,
):
    print("--------------------------------------------------")
    return await run_agent_with_prompt(
        user_prompt, repo, access_token, socket_id, session_id, llm_model_type, llm_model_name
    )
 