# backend-server/app/services/categorization.py
from app.schemas.activity import ActivityLogEntry
from app.core.config import settings
import requests

def classify_with_ai(window_title: str) -> str:
    """
    Calls the Perplexity AI API to classify a window title as 'Work' or 'Private'.
    """
    api_key = settings.PERPLEXITY_AI_API_KEY
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "llama-3-sonar-small-32k-online",
        "messages": [
            {
                "role": "system",
                "content": "You are an expert AI that classifies a web browser window title as 'Work' or 'Private'. Respond with only one of those two words.",
            },
            {"role": "user", "content": f"Classify this title: {window_title}"},
        ],
    }

    try:
        response = requests.post(
            "https://api.perplexity.ai/chat/completions",
            headers=headers,
            json=payload,
            timeout=15
        )
        response.raise_for_status()  # Raises an HTTPError for bad responses (4xx or 5xx)
        
        data = response.json()
        ai_response = data['choices'][0]['message']['content'].strip()
        
        # Ensure the response is one of the valid categories
        if ai_response in ["Work", "Private"]:
            return ai_response
        else:
            # If the AI gives an unexpected response, default to Private
            return "Private"
            
    except requests.exceptions.RequestException as e:
        # If the API call fails for any reason (network error, timeout, etc.), default to Private
        print(f"AI API call failed: {e}")
        return "Private"

def classify_activity(log: ActivityLogEntry) -> tuple[str, str | None]:
    """
    Classifies a raw activity log into a category ('Work', 'Private', 'Idle')
    and determines the details to be saved.
    """
    if log.state == "idle":
        return "Idle", None

    # Ensure app and title are not None for processing
    app_name = log.app.lower() if log.app else ""
    window_title = log.title if log.title else ""
    details = f"{log.app} - {log.title}" if log.app and log.title else log.app or log.title

    # --- Rule-based classification for known applications ---
    work_apps = ["code.exe", "visual studio code", "figma", "pycharm", "postman"]
    if any(app in app_name for app in work_apps):
        return "Work", details
        
    private_apps = ["netflix", "spotify", "steam", "discord"]
    if any(app in app_name for app in private_apps):
        # Privacy Guarantee: Never save details for private apps
        return "Private", None

    # --- AI-powered classification for ambiguous cases (e.g., a browser) ---
    if "chrome.exe" in app_name or "firefox.exe" in app_name or "safari" in app_name:
        if not window_title:
             return "Private", None # Cannot classify without a title
        
        category = classify_with_ai(window_title)
        return category, details if category == "Work" else None
    
    # Default to Private if no specific rules match
    return "Private", None