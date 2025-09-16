import json
from typing import List, Tuple
from pydantic import BaseModel
from llm_models.model import Model

# This is the Pydantic model for the structured output of the Analyst agent.
class AgentResponse(BaseModel):
    plan: str
    file_contents: List[Tuple[str, str]]

def parse_agent_response(raw_response_string: str) -> AgentResponse:
    """
    Parses the raw JSON string output from the Analyst agent,
    which may be nested inside another JSON object and contain markdown formatting.
    """
    # First, try to load the string as a JSON object to see if it's nested.
    try:
        outer_data = json.loads(raw_response_string)
        # If it is nested, the actual data is in the 'message' field.
        if 'message' in outer_data:
            message_string = outer_data['message']
        else:
            # If not nested, the raw string itself is the data.
            message_string = raw_response_string
    except json.JSONDecodeError:
        # If it's not a valid JSON object, it's likely just a string.
        message_string = raw_response_string

    # Clean the string by removing the markdown code fence and any whitespace.
    cleaned_message_string = message_string.strip().strip('```json').strip()

    # Parse the cleaned inner JSON string into a Python dictionary.
    inner_data = json.loads(cleaned_message_string)

    # Create and return a validated Pydantic model instance.
    return AgentResponse(**inner_data)

def get_code_changes(user_prompt: str, raw_analyst_output: str, llm_model: Model):
    """
    Takes the raw output from the Analyst agent, parses it,
    and then prepares the prompt for the Coder LLM to get the code changes.
    """
    # Parse the Analyst's messy response into a clean, structured object.
    try:
        analyst_response = parse_agent_response(raw_analyst_output)
    except Exception as e:
        print(f"Error parsing analyst response: {e}")
        return None, None

    response = llm_model.generate_content(user_prompt, analyst_response)
    
    print('LLM Response: ', response)
    return response, analyst_response.file_contents
