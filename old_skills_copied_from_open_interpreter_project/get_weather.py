"""Get current weather for a location using wttr.in (no API key required)."""

import requests


def get_weather(location="London"):
    """
    Fetch current weather for a location via wttr.in.

    Args:
        location: City name or location string (default: London).

    Returns:
        Dict with keys: location, condition, temp_c, temp_f, feels_like_c,
        humidity, wind_kph, description.
    """
    url = f"https://wttr.in/{requests.utils.quote(location)}"
    params = {"format": "j1"}  # JSON format
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    current = data["current_condition"][0]
    area = data["nearest_area"][0]
    area_name = area["areaName"][0]["value"]
    country = area["country"][0]["value"]

    condition   = current["weatherDesc"][0]["value"]
    temp_c      = int(current["temp_C"])
    feels_like  = int(current["FeelsLikeC"])
    humidity    = int(current["humidity"])
    wind_kph    = int(current["windspeedKmph"])
    location    = f"{area_name}, {country}"

    return (
        f"**{location}**\n"
        f"{condition}\n"
        f"🌡 {temp_c}°C (feels like {feels_like}°C)\n"
        f"💧 Humidity: {humidity}%\n"
        f"🌬 Wind: {wind_kph} km/h"
    )


if __name__ == "__main__":
    print(get_weather("London"))
