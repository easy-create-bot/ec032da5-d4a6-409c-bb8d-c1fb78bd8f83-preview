from gpt import GPT
from openai import OpenAI
from claude import Claude
import anthropic
from dotenv import load_dotenv
import os

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
claude = Claude("claude-opus-4-20250514", client)
print(claude.generate_content("Hello, how are you?"))