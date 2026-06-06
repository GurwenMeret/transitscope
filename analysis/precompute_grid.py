import asyncio
import aiohttp
import numpy as np
import alphashape
import json
import psycopg2
from datetime import datetime
from shapely.geometry import mapping, shape
from pathlib import Path
import yaml
import os
from dotenv import load_dotenv

load_dotenv()

OTP_URL = "http://localhost:8080/otp/gtfs/v1"
CONFIG_DIR = Path("config/cities")

DB_CONFIG = {
    "host": "localhost",
    "database": "transitscope",
    "user": "postgres",
    "password": os.getenv("POSTGRES_PASSWORD"),
    "port": 5432,
}

TRANSPORT_MODES = {
    "transit": [{"mode": "BUS"}, {"mode": "SUBWAY"}, {"mode": "WALK"}],
    "bicycle": [{"mode": "BICYCLE"}],
    "walk":    [{"mode": "WALK"}],
}

GRID_SPACING_DEG = 0.0025  # ~250m
MAX_CONCURRENT = 20  # requêtes parallèles


def load_city_config(city: str) -> dict:
    config_path = CONFIG_DIR / f"{city}.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def generate_grid(bbox: dict) -> list[tuple]:
    """Génère une grille de points espacés de ~250m sur la bbox."""
    lats = np.arange(bbox["south"], bbox["north"], GRID_SPACING_DEG)
    lons = np.arange(bbox["west"], bbox["east"], GRID_SPACING_DEG)
    points = [(round(lat, 6), round(lon, 6)) for lat in lats for lon in lons]
    print(f"Grille générée : {len(points)} points")
    return points


async def get_travel_time_async(
    session: aiohttp.ClientSession,
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    modes: list[dict],
    departure_time: datetime,
) -> float | None:
    """Version asynchrone du calcul de temps de trajet."""
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
        async with session.post(
            OTP_URL,
            json={"query": query},
            headers={"Content-Type": "application/json"},
            timeout=aiohttp.ClientTimeout(total=10),
        ) as response:
            data = await response.json()
            itineraries = data["data"]["plan"]["itineraries"]
            if itineraries:
                return itineraries[0]["duration"] / 60
    except Exception:
        pass
    return None


async def compute_isochrone_async(
    session: aiohttp.ClientSession,
    origin_lat: float,
    origin_lon: float,
    departure_time: datetime,
    max_minutes: int,
    mode_name: str,
    grid: list[tuple],
    semaphore: asyncio.Semaphore,
) -> dict | None:
    """Calcule un isochrone polygonal de façon asynchrone."""
    modes = TRANSPORT_MODES[mode_name]

    async def fetch_with_semaphore(lat, lon):
        async with semaphore:
            return await get_travel_time_async(
                session, origin_lat, origin_lon, lat, lon, modes, departure_time
            )

    tasks = [fetch_with_semaphore(lat, lon) for lat, lon in grid]
    times = await asyncio.gather(*tasks)

    reachable = [
        (lon, lat)
        for (lat, lon), t in zip(grid, times)
        if t is not None and t <= max_minutes
    ]

    if len(reachable) < 4:
        return None

    polygon = alphashape.alphashape(reachable, 5.0)

    return {
        "polygon": mapping(polygon),
        "reachable_points": len(reachable),
    }


def save_to_postgis(
    city: str,
    grid_lat: float,
    grid_lon: float,
    mode: str,
    max_minutes: int,
    departure_hour: int,
    geojson_polygon: dict,
    reachable_points: int,
) -> None:
    """Sauvegarde un isochrone dans PostGIS."""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO isochrone_grid 
            (city, grid_lat, grid_lon, mode, max_minutes, departure_hour, geom, reachable_points)
        VALUES 
            (%s, %s, %s, %s, %s, %s, ST_GeomFromGeoJSON(%s), %s)
        ON CONFLICT DO NOTHING
    """, (
        city, float(grid_lat), float(grid_lon), mode, max_minutes, departure_hour,
        json.dumps(geojson_polygon), reachable_points
    ))

    conn.commit()
    cur.close()
    conn.close()


async def precompute_city(city: str, departure_hour: int = 8, max_minutes: int = 30):
    """Précalcule tous les isochrones pour une ville."""
    config = load_city_config(city)
    bbox = config["bbox"]
    grid = generate_grid(bbox)

    departure_time = datetime.now().replace(
        hour=departure_hour, minute=0, second=0, microsecond=0
    )

    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    async with aiohttp.ClientSession() as session:
        for mode_name in TRANSPORT_MODES:
            print(f"\n=== Mode : {mode_name} ===")
            processed = 0

            for origin_lat, origin_lon in grid:
                result = await compute_isochrone_async(
                    session, origin_lat, origin_lon,
                    departure_time, max_minutes,
                    mode_name, grid, semaphore,
                )

                if result:
                    save_to_postgis(
                        city, origin_lat, origin_lon,
                        mode_name, max_minutes, departure_hour,
                        result["polygon"], result["reachable_points"],
                    )

                processed += 1
                if processed % 10 == 0:
                    print(f"  {processed}/{len(grid)} points traités")


if __name__ == "__main__":
    import asyncio
    print("Précalcul des isochrones — Montréal")
    print("ATTENTION : ce script prend plusieurs heures à compléter.")
    print("Il peut être interrompu et relancé — les points déjà calculés sont ignorés.")
    asyncio.run(precompute_city("montreal", departure_hour=8))