import os
import requests
from google.transit import gtfs_realtime_pb2
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

STM_CLIENT_ID = os.getenv("STM_CLIENT_ID")
STM_CLIENT_SECRET = os.getenv("STM_CLIENT_SECRET")

GTFS_RT_FEEDS = {
    "montreal": {
        "trip_updates": "https://api.stm.info/pub/od/gtfs-rt/ic/v2/tripUpdates",
        "vehicle_positions": "https://api.stm.info/pub/od/gtfs-rt/ic/v2/vehiclePositions",
        "alerts": "https://api.stm.info/pub/od/i3/v2/messages/etatservice",
    }
}

HEADERS = {
    "apikey": STM_CLIENT_ID,
    "client_secret": STM_CLIENT_SECRET,
}


def fetch_feed(url: str) -> gtfs_realtime_pb2.FeedMessage:
    """Télécharge et décode un flux GTFS-RT depuis une URL."""
    response = requests.get(url, headers=HEADERS, timeout=10)
    response.raise_for_status()

    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(response.content)
    return feed


def parse_trip_updates(feed: gtfs_realtime_pb2.FeedMessage) -> list[dict]:
    """Extrait les retards par trajet depuis un flux TripUpdates."""
    updates = []

    for entity in feed.entity:
        if not entity.HasField("trip_update"):
            continue

        trip = entity.trip_update.trip
        for stop_update in entity.trip_update.stop_time_update:
            delay = None

            if stop_update.HasField("departure"):
                delay = stop_update.departure.delay
            elif stop_update.HasField("arrival"):
                delay = stop_update.arrival.delay

            if delay is not None:
                updates.append({
                    "trip_id": trip.trip_id,
                    "route_id": trip.route_id,
                    "stop_id": stop_update.stop_id,
                    "delay_seconds": delay,
                    "timestamp": datetime.now().isoformat(),
                })

    return updates


def parse_alerts(feed: gtfs_realtime_pb2.FeedMessage) -> list[dict]:
    """Extrait les alertes de perturbation depuis un flux ServiceAlerts."""
    alerts = []

    for entity in feed.entity:
        if not entity.HasField("alert"):
            continue

        alert = entity.alert
        header = ""
        description = ""

        for translation in alert.header_text.translation:
            if translation.language in ("fr", ""):
                header = translation.text
                break

        for translation in alert.description_text.translation:
            if translation.language in ("fr", ""):
                description = translation.text
                break

        affected_routes = [
            selector.route_id
            for selector in alert.informed_entity
            if selector.route_id
        ]

        alerts.append({
            "id": entity.id,
            "header": header,
            "description": description,
            "affected_routes": affected_routes,
            "timestamp": datetime.now().isoformat(),
        })

    return alerts

def fetch_service_status(url: str) -> dict:
    """Télécharge l'état du service STM (format JSON)."""
    response = requests.get(url, headers=HEADERS, timeout=10)
    response.raise_for_status()
    return response.json()

def parse_service_status(data: dict) -> list[dict]:
    """Extrait les alertes depuis la réponse JSON État du Service STM."""
    alerts = []
    for alert in data.get("alerts", []):
        affected_routes = [
            e["route_short_name"]
            for e in alert.get("informed_entities", [])
            if "route_short_name" in e
        ]
        alerts.append({
            "affected_routes": affected_routes,
            "cause": alert.get("cause"),
            "effect": alert.get("effect"),
            "start": alert.get("active_periods", {}).get("start"),
            "end": alert.get("active_periods", {}).get("end"),
        })
    return alerts

def summarize(city: str) -> None:
    """Télécharge et résume les flux GTFS-RT d'une ville."""
    feeds = GTFS_RT_FEEDS.get(city)
    if not feeds:
        print(f"Ville inconnue : {city}")
        return

    print(f"\n--- TripUpdates ({city}) ---")
    try:
        feed = fetch_feed(feeds["trip_updates"])
        updates = parse_trip_updates(feed)
        print(f"  Mises à jour de trajets : {len(updates)}")
        if updates:
            exemple = updates[0]
            print(f"  Exemple — ligne {exemple['route_id']}, "
                  f"retard : {exemple['delay_seconds']}s")
    except Exception as e:
        print(f"  Erreur TripUpdates : {e}")

    print(f"\n--- État du service ({city}) ---")
    try:
        data = fetch_service_status(feeds["alerts"])
        alerts = parse_service_status(data)
        print(f"  Alertes actives : {len(alerts)}")
        if alerts:
            a = alerts[0]
            print(f"  Exemple — lignes affectées : {a['affected_routes']}")
    except Exception as e:
        print(f"  Erreur état du service : {e}")


if __name__ == "__main__":
    summarize("montreal")