import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL = "claude-sonnet-4-6"

FACILITY = {
    "name": "MASA SAUNA",
    "location": "Bangkok, Thailand",
    "languages": ["ja", "en", "th"],
    "targets": ["expats", "thai_affluent", "tourists", "health_conscious"],
}
