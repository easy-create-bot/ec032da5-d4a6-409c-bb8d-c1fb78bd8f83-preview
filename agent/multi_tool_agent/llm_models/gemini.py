from .model import Model
from google import genai
from dotenv import load_dotenv
import os
load_dotenv()

class Gemini(Model):
    models = {"gemini-1.5-flash", "gemini-2.0-flash", "gemini-2.5-pro", "gemini-2.5-flash"}
    def __init__(self, name: str):
        if name not in self.models:
            raise ValueError(f"Gemini: {name} is not a valid model")
        super().__init__(name)
        self.client = genai.Client()
    
    def generate_content(self, user_prompt: str, analyst_response) -> str:
        fix_prompt = self.get_fix_prompt(user_prompt, analyst_response)
        response = self.client.models.generate_content(
            model=self.name,
            contents=[fix_prompt]
        )
        return response.text    
