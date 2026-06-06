import os
import sys
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

from analysis.isochrone_ors import get_all_isochrones
from analysis.accessibility import compute_min_access_time
from datetime import datetime

app = FastAPI(title="TransitScope Python API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/isochrones")
def isochrones(lat: float, lon: float, minutes: int = 30):
    """Isochrones marche et vélo via ORS."""
    try:
        result = get_all_isochrones(lat, lon, minutes)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/accessibility")
def accessibility(lat: float, lon: float, city: str = "montreal", hour: int = 8):
    """Temps d'accès minimal par mode et catégorie de POI."""
    try:
        departure_time = datetime.now().replace(
            hour=hour, minute=0, second=0, microsecond=0
        )
        result = compute_min_access_time(lat, lon, departure_time, city)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health():
    return {"status": "ok", "service": "transitscope-python-api"}