from .model import Model
from openai import OpenAI
from pydantic import BaseModel
from typing import List
import os
from dotenv import load_dotenv
load_dotenv()

class Change(BaseModel):
    is_new_file: bool
    file_path: str
    action: str
    start_line: int
    end_line: int
    new_code: str

class GPTResponse(BaseModel):
    pr_description: str
    changes: List[Change]

class GPT(Model):
    def __init__(self, name: str):
        super().__init__(name)
        self.client = OpenAI(api_key=os.getenv("API_KEY_OPENAI"))
    
    def generate_content(self, user_prompt: str, analyst_response) -> str:
        fix_prompt = self.get_fix_prompt(user_prompt, analyst_response)
        response = self.client.chat.completions.parse(
            model=self.name,
            messages=[{"role": "user", "content": fix_prompt}],
            response_format=GPTResponse
        )
        return response.choices[0].message.content

    