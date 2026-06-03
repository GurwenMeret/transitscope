import requests
import json
from datetime import datetime
from pathlib import Path
import geopandas as gpd
from shapely.geometry import Point
import yaml

OTP_URL = "http://localhost:8080/otp/gtfs/v1"
CONFIG_DIR = Path("config/cities")


def load_city_config(city: str) -> dict:
    """Charge la configuration d'une ville depuis son fichier YAML."""
    config_path = CONFIG_DIR / f"{city}.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def query_isochrone(
    origin_lat: float,
    origin_lon: float,
    departure_time: datetime,
    max_time_minutes: int = 30,
) -> list[dict]:
    """Calcule les temps de trajet depuis un point via OTP GraphQL."""

    date_str = departure_time.strftime("%Y-%m-%d")
    time_str = departure_time.strftime("%H:%M:%S")

    query = f"""
    {{
      plan(
        from: {{lat: {origin_lat}, lon: {origin_lon}}}
        to: {{lat: 45.5048, lon: -73.6142}}
        date: "{date_str}"
        time: "{time_str}"
        numItineraries: 1
        transportModes: [
          {{mode: BUS}},
          {{mode: SUBWAY}},
          {{mode: WALK}}
        ]
      ) {{
        itineraries {{
          duration
          legs {{
            mode
            distance
            from {{ name lat lon }}
            to {{ name lat lon }}
          }}
        }}
      }}
    }}
    """

    response = requests.post(
        OTP_URL,
        json={"query": query},
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def compute_accessibility(
    origin_lat: float,
    origin_lon: float,
    departure_time: datetime,
    destinations: gpd.GeoDataFrame,
    max_time_minutes: int = 30,
) -> gpd.GeoDataFrame:
    """
    Calcule l'accessibilité depuis un point d'origine vers
    une liste de destinations.
    Retourne les destinations atteignables dans le temps imparti.
    """
    results = []

    for _, dest in destinations.iterrows():
        query = """
        {
          plan(
            from: {lat: %f, lon: %f}
            to: {lat: %f, lon: %f}
            date: "%s"
            time: "%s"
            numItineraries: 1
            transportModes: [
              {mode: BUS},
              {mode: SUBWAY},
              {mode: WALK}
            ]
          ) {
            itineraries {
              duration
            }
          }
        }
        """ % (
            origin_lat, origin_lon,
            dest.geometry.y, dest.geometry.x,
            departure_time.strftime("%Y-%m-%d"),
            departure_time.strftime("%H:%M:%S"),
        )

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
                duration_seconds = itineraries[0]["duration"]
                if duration_seconds <= max_time_minutes * 60:
                    results.append({
                        "name": dest.get("name", ""),
                        "duration_min": round(duration_seconds / 60, 1),
                        "geometry": dest.geometry,
                    })
        except Exception:
            continue

    if results:
        return gpd.GeoDataFrame(results, crs="EPSG:4326")
    return gpd.GeoDataFrame(columns=["name", "duration_min", "geometry"])


if __name__ == "__main__":
    print("Test OTP — itinéraire depuis Place-des-Arts vers UdeM")

    result = query_isochrone(
        origin_lat=45.5088,
        origin_lon=-73.5690,
        departure_time=datetime(2026, 6, 3, 8, 0, 0),
        max_time_minutes=30,
    )

    itineraries = result["data"]["plan"]["itineraries"]
    print(f"Itinéraires trouvés : {len(itineraries)}")
    for i, itin in enumerate(itineraries):
        print(f"  [{i+1}] Durée : {round(itin['duration']/60, 1)} min")
        for leg in itin["legs"]:
            print(f"       {leg['mode']} — {round(leg['distance'])}m")