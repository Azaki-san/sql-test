import httpx
from datetime import datetime


def get_weather():
    try:
        resp = httpx.get("https://wttr.in/?format=j1", timeout=5)
        data = resp.json()
        current = data["current_condition"][0]
        res = {
            "temp_C": current["temp_C"],
            "weatherDesc": current["weatherDesc"][0]["value"],
        }
        if datetime.now().hour < 6 or datetime.now().hour > 20:
            res["time_of_day"] = "night"
        else:
            res["time_of_day"] = "day"
        return res
    except Exception as e:
        return {"error": str(e)}
