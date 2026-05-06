import os
from dotenv import load_dotenv

load_dotenv()

def _load_api_key() -> str:
    if key := os.getenv("ANTHROPIC_API_KEY"):
        return key
    token_file = "/home/claude/.claude/remote/.session_ingress_token"
    try:
        with open(token_file) as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""

ANTHROPIC_API_KEY = _load_api_key()
MODEL = "claude-sonnet-4-6"

FACILITY = {
    "name": "MASA SAUNA",
    "location": "Bangkok, Thailand",
    "languages": ["ja", "en", "th"],
    "targets": ["expats", "thai_affluent", "tourists", "health_conscious"],
}
