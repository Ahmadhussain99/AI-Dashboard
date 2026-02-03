"""
Test Gemini API with new Google GenAI SDK and Retry Logic
"""
import os
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

# --- CONFIGURATION ---
# Models like 'gemini-2.0-flash-exp' have lower free-tier limits.
# If errors persist, try 'gemini-1.5-flash'.
MODEL_NAME = 'gemini-1.5-flash'  # Much more reliable for free-tier testing

print(f"Testing Gemini API ({MODEL_NAME})\n" + "="*50)

api_key = os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY')

if not api_key:
    print("\n❌ No API key found!")
    exit(1)

# Initialize client with Retry Config
# This tells the SDK to retry up to 3 times if it hits a 429 (Resource Exhausted) error.
# Initialize client with the correct Retry Object structure
client = genai.Client(
    api_key=api_key,
    http_options=types.HttpOptions(
        retry_config=types.HttpRetryOptions(
            max_attempts=3  # Use 'max_attempts' instead of 'retries'
        )
    )
)

def run_test():
    try:
        print("\n🔄 Testing API connection...")
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents='Say "Gemini API is working!"',
            config=types.GenerateContentConfig(
                temperature=0,
                max_output_tokens=100,
            )
        )
        print(f"✅ Gemini API is working! Response: {response.text}")

        # Test SQL generation
        print("\n🔄 Testing SQL generation...")
        sql_prompt = "Generate a SQL query to get all customers. Return JSON: {'sql': '...', 'explanation': '...'}"
        
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=sql_prompt,
            config=types.GenerateContentConfig(temperature=0)
        )
        print(f"✅ SQL Generation working! Response: {response.text[:100]}...")

    except Exception as e:
        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
            print("\n⚠️ Rate Limit Hit: The free tier is currently busy.")
            print("Try again in 60 seconds or switch to 'gemini-1.5-flash'.")
        else:
            print(f"\n❌ Test failed: {e}")

if __name__ == "__main__":
    run_test()
    print("\n" + "="*50)