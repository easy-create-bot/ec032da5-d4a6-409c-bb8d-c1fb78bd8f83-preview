from .model import Model
from anthropic import Anthropic
import os
from dotenv import load_dotenv
load_dotenv()

class Claude(Model):
    def __init__(self, name: str):
        super().__init__(name)
        self.client = Anthropic(api_key=os.getenv("API_KEY_ANTHROPIC"))
    
    def generate_content(self, user_prompt: str, analyst_response) -> str:
        fix_prompt = self.get_fix_prompt(user_prompt, analyst_response)
        
        # Add JSON formatting instruction to the prompt
        enhanced_prompt = f"{fix_prompt}\n\nIMPORTANT: Return ONLY a valid JSON object. Do not include any other text, explanations, or markdown formatting. The response must start with {{ and end with }}."
        
        print(enhanced_prompt)
        token_count = self.client.messages.count_tokens(
            model="claude-opus-4-1-20250805",
            system="You are a scientist",
            messages=[{"role": "user", "content": enhanced_prompt}],
        )
        print(token_count)
        
        response = self.client.messages.create(
            model=self.name,
            max_tokens=8192,  # Increased for comprehensive responses
            temperature=0.1,  # Lower temperature for more consistent JSON output
            messages=[{"role": "user", "content": enhanced_prompt}]
        )

        return response.content[0].text
    