import gtfs_kit as gk
import requests
import zipfile
import os
from pathlib import Path

DATA_DIR = Path("data/gtfs")

def download_gtfs(url: str, city_name: str) -> Path:
    """Télécharge le fichier GTFS d'une ville et le sauvegarde localement."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = DATA_DIR / f"{city_name}.zip"

    print(f"Téléchargement GTFS pour {city_name}...")
    response = requests.get(url, timeout=60)
    response.raise_for_status()

    with open(zip_path, "wb") as f:
        f.write(response.content)

    print(f"Sauvegardé : {zip_path}")
    return zip_path


def load_gtfs(zip_path: Path) -> gk.Feed:
    """Charge un fichier GTFS et retourne un objet Feed."""
    print(f"Chargement du feed GTFS : {zip_path}")
    feed = gk.read_feed(zip_path, dist_units="km")
    return feed


def summarize_feed(feed: gk.Feed) -> None:
    """Affiche un résumé du contenu du feed GTFS."""
    print(f"  Lignes    : {len(feed.routes)}")
    print(f"  Arrêts    : {len(feed.stops)}")
    print(f"  Trajets   : {len(feed.trips)}")


if __name__ == "__main__":
    # URL GTFS publique de la STM (Montréal)
    STM_GTFS_URL = "https://www.stm.info/sites/default/files/gtfs/gtfs_stm.zip"

    zip_path = download_gtfs(STM_GTFS_URL, "montreal")
    feed = load_gtfs(zip_path)
    summarize_feed(feed)