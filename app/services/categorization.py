# backend-server/app/services/categorization.py
from app.schemas.activity import ActivityLogEntry
from app.core.config import settings
import httpx  
import json

async def classify_with_ai(app_name: str, window_title: str) -> str:
    """
    Calls the Perplexity AI API asynchronously to classify an activity.
    """
    api_key = settings.PERPLEXITY_AI_API_KEY
    if not api_key:
        print("Error: PERPLEXITY_AI_API_KEY not set.")
        return "Private"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    system_prompt = (
        "You are an expert AI that classifies user activity based on a JSON object. "
        "I will provide an 'app' and a 'title'. Your response must be a valid JSON object "
        "containing a single key, 'category', with a value of either 'Work' or 'Private'. "
        "Do not include any other text, explanations, or markdown. "
        "Example Input: {\"app\": \"Code\", \"title\": \"main.py - MyProject\"} "
        "Example Output: {\"category\": \"Work\"} "
        "Example Input: {\"app\": \"spotify\", \"title\": \"Daily Mix 1\"} "
        "Example Output: {\"category\": \"Private\"} "
        "If the category is ambiguous, always default to 'Private'."
    )
    
    user_input = {
        "app": app_name,
        "title": window_title
    }
    
    payload = {
        "model": "sonar-pro",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_input)},
        ],
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "https://api.perplexity.ai/chat/completions",
                headers=headers,
                json=payload,
                timeout=30 # Increased timeout for AI
            )
            response.raise_for_status()
            
            ai_response_text = response.json()['choices'][0]['message']['content'].strip()
            response_data = json.loads(ai_response_text)
            category = response_data.get("category")
            
            return category if category in ["Work", "Private"] else "Private"
                
        except httpx.HTTPStatusError as http_err:
            print(f"❌ HTTP Error from Perplexity API: {http_err}")
            print(f"    Response Body: {http_err.response.text}")
            return "Private"
        except (httpx.RequestError, json.JSONDecodeError, KeyError) as e:
            print(f"AI API call or parsing failed: {e}")
            return "Private"

async def classify_activity(log: ActivityLogEntry) -> tuple[str, str | None]:
    """
    Asynchronously classifies an activity log and correctly formats the details string.
    """
    if log.state == "idle":
        return "Idle", None

    app = log.app or "Unknown"
    title = log.title or "Unknown"
    
    # This now correctly 'awaits' the async AI call
    category = await classify_with_ai(app, title)
    
    if category == "Work":
        if log.app and log.title:
            details = f"{log.app} - {log.title}"
        else:
            details = log.title or log.app
    else:
        details = None
    
    return category, details