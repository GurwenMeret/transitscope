import requests
from datetime import datetime
from pathlib import Path
import geopandas as gpd
from shapely.geometry import Point
import yaml

OTP_URL = "http://localhost:8080/otp/gtfs/v1"
CONFIG_DIR = Path("config/cities")

POI_CATEGORIES = {
    "health": {
        "label": "Santé",
        "overpass_tags": '["amenity"~"hospital|clinic|doctors|pharmacy"]',
    },
    "food": {
        "label": "Alimentation",
        "overpass_tags": '["shop"~"supermarket|grocery|convenience|market"]',
    },
    "park": {
        "label": "Parcs",
        "overpass_tags": '["leisure"="park"]',
    },
}

TRANSPORT_MODES = {
    "transit": [{"mode": "BUS"}, {"mode": "SUBWAY"}, {"mode": "WALK"}],
    "bicycle": [{"mode": "BICYCLE"}],
    "walk":    [{"mode": "WALK"}],
}


def load_city_config(city: str) -> dict:
    """Charge la configuration d'une ville depuis son fichier YAML."""
    config_path = CONFIG_DIR / f"{city}.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def fetch_poi(category: str, bbox: dict, max_results: int = 20) -> gpd.GeoDataFrame:
    """Télécharge les POI d'une catégorie via Overpass API."""
    tags = POI_CATEGORIES[category]["overpass_tags"]
    bbox_str = f"{bbox['south']},{bbox['west']},{bbox['north']},{bbox['east']}"

    query = f"""
    [out:json][timeout:30][bbox:{bbox_str}];
    (
      node{tags};
      way{tags};
    );
    out center {max_results};
    """

    response = requests.post(
        "https://overpass-api.de/api/interpreter",
        data={"data": query},
        headers={"User-Agent": "transitscope-portfolio/1.0"},
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()

    pois = []
    for element in data.get("elements", []):
        lat = element.get("lat") or element.get("center", {}).get("lat")
        lon = element.get("lon") or element.get("center", {}).get("lon")
        if lat and lon:
            pois.append({
                "name": element.get("tags", {}).get("name", "Sans nom"),
                "category": category,
                "geometry": Point(lon, lat),
            })

    # TODO: le plafond max_results=20 peut manquer le vrai POI le plus proche
    # si celui-ci est au-delà des 20 premiers retournés par Overpass.
    # Amélioration prévue : pré-trier par distance à vol d'oiseau (Shapely)
    # avant d'interroger OTP, et augmenter max_results progressivement.
    return gpd.GeoDataFrame(pois, crs="EPSG:4326")


def get_travel_time(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    modes: list[dict],
    departure_time: datetime,
) -> float | None:
    """Retourne le temps de trajet en minutes, ou None si non atteignable."""
    modes_str = ", ".join([f'{{mode: {m["mode"]}}}' for m in modes])
    date_str = departure_time.strftime("%Y-%m-%d")
    time_str = departure_time.strftime("%H:%M:%S")

    query = f"""
    {{
      plan(
        from: {{lat: {origin_lat}, lon: {origin_lon}}}
        to: {{lat: {dest_lat}, lon: {dest_lon}}}
        date: "{date_str}"
        time: "{time_str}"
        numItineraries: 1
        transportModes: [{modes_str}]
      ) {{
        itineraries {{
          duration
        }}
      }}
    }}
    """

    try:
        response = requests.post(
            OTP_URL,
            json={"query": query},
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        data = response.json()
        itineraries = data["data"]["plan"]["itineraries"]
        if itineraries:
            return round(itineraries[0]["duration"] / 60, 1)
    except Exception:
        pass
    return None


def compute_min_access_time(
    origin_lat: float,
    origin_lon: float,
    departure_time: datetime,
    city: str,
) -> dict:
    """
    Calcule le temps d'accès minimal par mode et par catégorie de POI.
    Retourne un dictionnaire structuré par catégorie et mode.
    """
    config = load_city_config(city)
    bbox = config["bbox"]
    results = {}

    for category in POI_CATEGORIES:
        print(f"  Catégorie : {POI_CATEGORIES[category]['label']}")
        pois = fetch_poi(category, bbox)
        print(f"    {len(pois)} POI trouvés")

        results[category] = {}

        for mode_name, modes in TRANSPORT_MODES.items():
            min_time = None

            for _, poi in pois.iterrows():
                t = get_travel_time(
                    origin_lat, origin_lon,
                    poi.geometry.y, poi.geometry.x,
                    modes, departure_time,
                )
                if t is not None:
                    if min_time is None or t < min_time:
                        min_time = t

            results[category][mode_name] = min_time
            print(f"    {mode_name:10} → {min_time} min")

    return results


if __name__ == "__main__":
    print("Test accessibilité — Place-des-Arts, Montréal, 8h00")
    results = compute_min_access_time(
        origin_lat=45.5088,
        origin_lon=-73.5690,
        departure_time=datetime(2026, 6, 3, 8, 0, 0),
        city="montreal",
    )

    print("\n--- Résultats ---")
    for category, modes in results.items():
        label = POI_CATEGORIES[category]["label"]
        print(f"\n{label}:")
        for mode, time in modes.items():
            print(f"  {mode:10} : {time} min")