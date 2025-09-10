import os
from openai import OpenAI

def _make_openai_client():
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY/OPENROUTER_API_KEY не задан")

    base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    headers = {
        "HTTP-Referer": os.getenv("OPENROUTER_REF", "https://t.me/slivochniyfootball"),
        "X-Title": os.getenv("OPENROUTER_TITLE", "Coffee Bot"),
    }
    return OpenAI(api_key=api_key, base_url=base_url, default_headers=headers)
