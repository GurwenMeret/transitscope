import requests
import subprocess
from pathlib import Path
import yaml
import osmium

OSM_DIR = Path("data/osm")
CONFIG_DIR = Path("config/cities")


def load_city_config(city: str) -> dict:
    """Charge la configuration d'une ville depuis son fichier YAML."""
    config_path = CONFIG_DIR / f"{city}.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def download_osm_pbf(city: str, url: str) -> Path:
    """Télécharge un fichier PBF depuis une URL."""
    OSM_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OSM_DIR / f"{city}_raw.pbf"

    print(f"Téléchargement OSM PBF pour {city}...")
    response = requests.get(url, stream=True, timeout=120)
    response.raise_for_status()

    total = 0
    with open(output_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
            total += len(chunk)
            print(f"\r  {total / 1024 / 1024:.1f} MB téléchargés...", end="")

    print(f"\nSauvegardé : {output_path}")
    return output_path

def crop_pbf(city: str, raw_path: Path, bbox: dict) -> Path:
    """Découpe le fichier PBF selon la bbox de la ville."""
    output_path = OSM_DIR / f"{city}.pbf"

    print(f"Découpage OSM selon la bbox...")

    left = bbox['west']
    bottom = bbox['south']
    right = bbox['east']
    top = bbox['north']

    with osmium.ForwardReferenceWriter(str(output_path), ref_src=str(raw_path), overwrite=True) as writer:
        for obj in osmium.FileProcessor(str(raw_path)):
            if isinstance(obj, osmium.osm.Node):
                if left <= obj.location.lon <= right and bottom <= obj.location.lat <= top:
                    writer.add_node(obj)

    print(f"Découpé : {output_path}")
    raw_path.unlink()
    return output_path


def bootstrap_osm(city: str) -> None:
    """Télécharge et prépare les données OSM pour une ville."""
    config = load_city_config(city)
    bbox = config["bbox"]
    raw_path = OSM_DIR / f"{city}_raw.pbf"

    if not raw_path.exists():
        geofabrik_url = "https://download.geofabrik.de/north-america/canada/quebec-latest.osm.pbf"
        raw_path = download_osm_pbf(city, geofabrik_url)
    else:
        print(f"Fichier raw existant trouvé : {raw_path}")

    crop_pbf(city, raw_path, bbox)
    print(f"OSM prêt pour {city}.")


if __name__ == "__main__":
    bootstrap_osm("montreal")