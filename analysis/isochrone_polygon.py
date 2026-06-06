import requests
import numpy as np
import alphashape
import json
from datetime import datetime
from shapely.geometry import mapping, Point
import geopandas as gpd

OTP_URL = "http://localhost:8080/otp/gtfs/v1"

TRANSPORT_MODES = {
    "transit": [{"mode": "BUS"}, {"mode": "SUBWAY"}, {"mode": "WALK"}],
    "bicycle": [{"mode": "BICYCLE"}],
    "walk":    [{"mode": "WALK"}],
}


def generate_grid(origin_lat: float, origin_lon: float, radius_deg: float = 0.08, n: int = 15) -> list[tuple]:
    """Génère une grille de points autour de l'origine."""
    lats = np.linspace(origin_lat - radius_deg, origin_lat + radius_deg, n)
    lons = np.linspace(origin_lon - radius_deg, origin_lon + radius_deg, n)
    return [(lat, lon) for lat in lats for lon in lons]


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
            timeout=8,
        )
        data = response.json()
        itineraries = data["data"]["plan"]["itineraries"]
        if itineraries:
            return itineraries[0]["duration"] / 60
    except Exception:
        pass
    return None


def compute_isochrone_polygon(
    origin_lat: float,
    origin_lon: float,
    departure_time: datetime,
    max_minutes: int = 30,
    mode_name: str = "transit",
    alpha: float = 5.0,
) -> dict | None:
    """
    Calcule un polygone isochrone pour un mode donné.
    Retourne un GeoJSON Feature ou None si pas assez de points.
    """
    modes = TRANSPORT_MODES[mode_name]
    grid = generate_grid(origin_lat, origin_lon)

    print(f"  Calcul isochrone {mode_name} ({len(grid)} points)...")
    reachable = []

    for i, (lat, lon) in enumerate(grid):
        t = get_travel_time(origin_lat, origin_lon, lat, lon, modes, departure_time)
        if t is not None and t <= max_minutes:
            reachable.append((lon, lat))
        if (i + 1) % 50 == 0:
            print(f"    {i + 1}/{len(grid)} points traités, {len(reachable)} atteignables")

    print(f"  {len(reachable)} points atteignables sur {len(grid)}")

    if len(reachable) < 4:
        print(f"  Pas assez de points pour générer un polygone")
        return None

    polygon = alphashape.alphashape(reachable, alpha)

    return {
        "type": "Feature",
        "properties": {
            "mode": mode_name,
            "max_minutes": max_minutes,
            "reachable_points": len(reachable),
        },
        "geometry": mapping(polygon),
    }


def compute_all_isochrones(
    origin_lat: float,
    origin_lon: float,
    departure_time: datetime,
    max_minutes: int = 30,
) -> dict:
    """Calcule les isochrones pour tous les modes."""
    results = {}
    for mode_name in TRANSPORT_MODES:
        print(f"\nMode : {mode_name}")
        feature = compute_isochrone_polygon(
            origin_lat, origin_lon,
            departure_time, max_minutes,
            mode_name,
        )
        if feature:
            results[mode_name] = feature

    return {
        "type": "FeatureCollection",
        "features": list(results.values()),
    }


if __name__ == "__main__":
    print("Test isochrone polygonal — Place-des-Arts, 8h00, 30 min")
    result = compute_all_isochrones(
        origin_lat=45.5088,
        origin_lon=-73.5690,
        departure_time=datetime(2026, 6, 5, 8, 0, 0),
        max_minutes=30,
    )

    print(f"\nRésultat : {len(result['features'])} isochrones générés")
    for feature in result["features"]:
        props = feature["properties"]
        print(f"  {props['mode']} : {props['reachable_points']} points atteignables")

    with open("data/isochrones_test.geojson", "w") as f:
        json.dump(result, f, indent=2)
    print("\nSauvegardé : data/isochrones_test.geojson")