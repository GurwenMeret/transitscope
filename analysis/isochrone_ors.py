import requests
import os
from dotenv import load_dotenv

load_dotenv()

ORS_API_KEY = os.getenv("ORS_API_KEY")
ORS_URL = "https://api.openrouteservice.org/v2/isochrones"

ORS_PROFILES = {
    "walk": "foot-walking",
    "bicycle": "cycling-regular",
}


def get_isochrone(lat: float, lon: float, mode: str, minutes: int = 30) -> dict | None:
    profile = ORS_PROFILES.get(mode)
    if not profile:
        return None

    try:
        response = requests.post(
            f"{ORS_URL}/{profile}",
            headers={
                "Authorization": ORS_API_KEY,
                "Content-Type": "application/json",
            },
            json={
                "locations": [[lon, lat]],
                "range": [minutes * 60],
                "range_type": "time",
            },
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        features = data.get("features", [])
        if not features:
            return None

        return {
            "type": "Feature",
            "properties": {"mode": mode, "max_minutes": minutes},
            "geometry": features[0]["geometry"],
        }
    except Exception:
        return None


def get_all_isochrones(lat: float, lon: float, minutes: int = 30) -> dict:
    """Retourne les isochrones marche et vélo depuis ORS."""
    features = []
    for mode in ORS_PROFILES:
        feature = get_isochrone(lat, lon, mode, minutes)
        if feature:
            features.append(feature)

    return {"type": "FeatureCollection", "features": features}