from app.config import get_settings
from google import genai
from google.genai import errors

settings = get_settings()
client = genai.Client(api_key=settings.gemini_api_key)

candidates = [
    "gemini-3.1-flash-lite",
    "gemini-3-flash-preview",
    "gemini-3.5-flash",
    "gemini-2.5-flash-lite",
]

for model_name in candidates:
    try:
        response = client.models.generate_content(
            model=model_name,
            contents="Say hello in one sentence.",
        )
        print(f"✅ WORKS: {model_name} -> {response.text.strip()}")
    except errors.ClientError as e:
        print(f"❌ FAILED: {model_name} -> {e}")
