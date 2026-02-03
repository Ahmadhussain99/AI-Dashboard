"""
List all available Gemini models for your API key (google-genai SDK)
"""
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY')

if not api_key:
    print("[ERROR] No API key found in .env file")
    raise SystemExit(1)

print("Checking available Gemini models...")
print("=" * 60)

try:
    from google import genai

    client = genai.Client(api_key=api_key)

    # List all models
    print("[INFO] Available models:")
    print("")

    models_list = client.models.list()

    generation_models = []

    for model in models_list:
        model_name = getattr(model, "name", None) or getattr(model, "model", None) or "unknown-model"

        # Check for generation support if available
        methods = (
            getattr(model, "supported_actions", None)
            or getattr(model, "supported_generation_methods", None)
            or []
        )
        method_names = [str(m) for m in methods]
        if any(m in method_names for m in ("generateContent", "generate_content")):
            generation_models.append(model_name)
            print(f"[OK] {model_name}")
            display_name = getattr(model, "display_name", None)
            if display_name:
                print(f"   Display: {display_name}")
            if method_names:
                print(f"   Methods: {method_names}")
                print("")

    if generation_models:
        print("=" * 60)
        print("")
        print(f"[OK] Found {len(generation_models)} model(s) that support generateContent:")
        for model_name in generation_models:
            print(f"   - {model_name}")

        print("")
        print("[INFO] Use one of these model IDs in app.py:")
        print(f'   self.model = "{generation_models[0]}"')
    else:
        print("")
        print("[ERROR] No models found that support generateContent")
        print("This might be an API key issue or a permissions problem.")

except Exception as e:
    print(f"[ERROR] {e}")
    print("")
    print("Troubleshooting:")
    print("1. Check your API key is valid")
    print("2. Make sure you have API access enabled")
    print("3. Try regenerating your API key at https://aistudio.google.com/app/apikey")
