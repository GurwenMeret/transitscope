import requests
import subprocess
from pathlib import Path
import yaml

OSM_DIR = Path("data/osm")
CONFIG_DIR = Path("config/cities")
QUEBEC_RAW = OSM_DIR / "quebec_raw.pbf"
GEOFABRIK_URL = "https://download.geofabrik.de/north-america/canada/quebec-latest.osm.pbf"


def load_city_config(city: str) -> dict:
    config_path = CONFIG_DIR / f"{city}.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def download_quebec_pbf() -> Path:
    """Télécharge le fichier provincial une seule fois."""
    if QUEBEC_RAW.exists():
        print(f"Fichier provincial existant trouvé : {QUEBEC_RAW}")
        return QUEBEC_RAW

    OSM_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Téléchargement OSM PBF provincial...")
    response = requests.get(GEOFABRIK_URL, stream=True, timeout=120)
    response.raise_for_status()

    total = 0
    with open(QUEBEC_RAW, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
            total += len(chunk)
            print(f"\r  {total / 1024 / 1024:.1f} MB téléchargés...", end="", flush=True)

    print(f"\nSauvegardé : {QUEBEC_RAW}")
    return QUEBEC_RAW


def crop_pbf(city: str, polygon_path: Path) -> Path:
    """Découpe le fichier provincial selon le polygone de la ville."""
    output_path = OSM_DIR / f"{city}.pbf"

    print(f"Découpage OSM pour {city}...")
    subprocess.run([
        "osmium", "extract",
        "--polygon", str(polygon_path),
        "--strategy=simple",
        str(QUEBEC_RAW),
        "-o", str(output_path),
        "--overwrite"
    ], check=True)

    print(f"Découpé : {output_path}")
    return output_path


def bootstrap_osm(city: str) -> None:
    """Télécharge (si nécessaire) et découpe les données OSM pour une ville."""
    config = load_city_config(city)
    polygon_path = Path(config["polygon"])

    download_quebec_pbf()  # ne télécharge que si absent
    crop_pbf(city, polygon_path)
    print(f"OSM prêt pour {city}.")


def bootstrap_all() -> None:
    """Prépare les données OSM pour toutes les villes, puis supprime le raw."""
    cities = ["montreal", "quebec", "sherbrooke"]

    download_quebec_pbf()

    for city in cities:
        config = load_city_config(city)
        polygon_path = Path(config["polygon"])
        crop_pbf(city, polygon_path)
        print(f"OSM prêt pour {city}.")

    # Supprime le fichier provincial seulement après tous les découpages
    QUEBEC_RAW.unlink()
    print(f"\nFichier provincial supprimé. Tous les extraits sont prêts.")


if __name__ == "__main__":
    bootstrap_all()