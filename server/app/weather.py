"""
Hourly weather forecast for the courts (outdoor), from Open-Meteo: free, no key.
"""
import json
import urllib.parse
import urllib.request
from typing import Dict, List

# The padel courts at the Île de Loisirs de Cergy-Pontoise, as placed on the
# club's own activity map ("Padel tennis", cergy-pontoise.iledeloisirs.fr)
LATITUDE = 49.028824
LONGITUDE = 2.058013
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
FIELDS = ["temperature_2m", "precipitation_probability", "precipitation", "weather_code", "wind_speed_10m", "is_day"]


def fetch_hourly(days: int) -> Dict[str, Dict[str, List]]:
    """{"2026-10-17": {"19": [temp °C, rain chance %, rain mm, WMO code, wind km/h, is_day]}}.
    Rain chance is null for the furthest days, where Open-Meteo does not give it."""
    query = urllib.parse.urlencode({
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "hourly": ",".join(FIELDS),
        "timezone": "Europe/Paris",
        "forecast_days": min(days, 16),
    })
    with urllib.request.urlopen(f"{FORECAST_URL}?{query}", timeout=20) as response:
        hourly = json.loads(response.read())["hourly"]

    weather: Dict[str, Dict[str, List]] = {}
    for i, stamp in enumerate(hourly["time"]):  # "2026-10-17T19:00", Paris time
        day, hour = stamp[:10], str(int(stamp[11:13]))
        weather.setdefault(day, {})[hour] = [hourly[f][i] for f in FIELDS]
    return weather
