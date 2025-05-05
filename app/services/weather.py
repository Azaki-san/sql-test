import httpx
from datetime import datetime

def get_weather():
    try:
        resp = httpx.get("https://wttr.in/?format=j1", timeout=5)
        data = resp.json()
        current = data["current_condition"][0]
        return {
            "temp_C": current["temp_C"],
            "weatherDesc": current["weatherDesc"][0]["value"],
            "time_of_day": "night" if datetime.now().hour < 6 or datetime.now().hour > 20 else "day"
        }
    except Exception as e:
        return {"error": str(e)}