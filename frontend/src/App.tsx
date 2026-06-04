import { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import "./App.css";

const API_URL = "http://localhost:5062";

interface Leg {
  mode: string;
  distance: number;
}

interface Itinerary {
  duration: number;
  legs: Leg[];
}

interface AccessibilityCategory {
  category: string;
  transit: number;
  bicycle: number;
  walk: number;
}

export default function App() {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const [time, setTime] = useState("08:00");
  const [itineraries, setItineraries] = useState<Itinerary[]>([]);
  const [accessibility, setAccessibility] = useState<AccessibilityCategory[]>(
    [],
  );
  const [loading, setLoading] = useState(false);
  const [selectedPoint, setSelectedPoint] = useState<
    { lat: number; lon: number } | null
  >(null);

  useEffect(() => {
    if (map.current || !mapContainer.current) return;

    map.current = new maplibregl.Map({
      container: mapContainer.current,
      style: "https://demotiles.maplibre.org/style.json",
      center: [-73.5690, 45.5088],
      zoom: 12,
    });

    map.current.addControl(new maplibregl.NavigationControl());

    map.current.on("click", async (e) => {
      const { lat, lng: lon } = e.lngLat;
      setSelectedPoint({ lat, lon });
      setLoading(true);

      try {
        const [isoRes, accRes] = await Promise.all([
          fetch(
            `${API_URL}/api/isochrone?lat=${lat}&lon=${lon}&time=${time}:00&maxMinutes=30`,
          ),
          fetch(
            `${API_URL}/api/accessibility?lat=${lat}&lon=${lon}&city=montreal&time=${time}:00`,
          ),
        ]);

        const isoData = await isoRes.json();
        const accData = await accRes.json();

        setItineraries(isoData?.data?.plan?.itineraries ?? []);
        setAccessibility(accData?.categories ?? []);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    });
  }, []);

  return (
    <div style={{ display: "flex", height: "100vh", width: "100vw" }}>
      {/* Carte */}
      <div ref={mapContainer} style={{ flex: 1 }} />

      {/* Panel latéral */}
      <div
        style={{
          width: "340px",
          background: "#1a1a2e",
          color: "#eee",
          padding: "20px",
          overflowY: "auto",
          fontFamily: "sans-serif",
        }}
      >
        <h2 style={{ color: "#4fc3f7", marginTop: 0 }}>TransitScope</h2>
        <p style={{ fontSize: "13px", color: "#aaa" }}>
          Cliquez sur la carte pour analyser l'accessibilité d'un point.
        </p>

        {/* Slider horaire */}
        <div style={{ marginBottom: "20px" }}>
          <label style={{ fontSize: "13px" }}>
            Heure de départ : <strong>{time}</strong>
          </label>
          <input
            type="range"
            min="6"
            max="23"
            value={parseInt(time)}
            onChange={(e) => setTime(`${e.target.value.padStart(2, "0")}:00`)}
            style={{ width: "100%", marginTop: "8px" }}
          />
        </div>

        {loading && <p style={{ color: "#4fc3f7" }}>Calcul en cours...</p>}

        {selectedPoint && (
          <p style={{ fontSize: "12px", color: "#888" }}>
            Point : {selectedPoint.lat.toFixed(4)},{" "}
            {selectedPoint.lon.toFixed(4)}
          </p>
        )}

        {/* Itinéraires */}
        {itineraries.length > 0 && (
          <div style={{ marginBottom: "20px" }}>
            <h3 style={{ color: "#4fc3f7", fontSize: "14px" }}>
              Itinéraires (30 min)
            </h3>
            {itineraries.map((itin, i) => (
              <div
                key={i}
                style={{
                  background: "#16213e",
                  borderRadius: "8px",
                  padding: "10px",
                  marginBottom: "8px",
                  fontSize: "13px",
                }}
              >
                <strong>{Math.round(itin.duration / 60)} min</strong>
                <div style={{ marginTop: "4px" }}>
                  {itin.legs.map((leg, j) => (
                    <span
                      key={j}
                      style={{
                        background: leg.mode === "SUBWAY"
                          ? "#7c4dff"
                          : leg.mode === "BUS"
                          ? "#00897b"
                          : "#555",
                        color: "#fff",
                        borderRadius: "4px",
                        padding: "2px 6px",
                        marginRight: "4px",
                        fontSize: "11px",
                      }}
                    >
                      {leg.mode} {Math.round(leg.distance)}m
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Accessibilité */}
        {accessibility.length > 0 && (
          <div>
            <h3 style={{ color: "#4fc3f7", fontSize: "14px" }}>
              Accessibilité
            </h3>
            {accessibility.map((cat) => (
              <div
                key={cat.category}
                style={{
                  background: "#16213e",
                  borderRadius: "8px",
                  padding: "10px",
                  marginBottom: "8px",
                  fontSize: "13px",
                }}
              >
                <strong style={{ textTransform: "capitalize" }}>
                  {cat.category}
                </strong>
                <div
                  style={{
                    marginTop: "6px",
                    display: "grid",
                    gridTemplateColumns: "1fr 1fr 1fr",
                    gap: "4px",
                  }}
                >
                  <div style={{ textAlign: "center" }}>
                    <div style={{ fontSize: "11px", color: "#888" }}>TC</div>
                    <div style={{ color: "#4fc3f7" }}>{cat.transit} min</div>
                  </div>
                  <div style={{ textAlign: "center" }}>
                    <div style={{ fontSize: "11px", color: "#888" }}>Vélo</div>
                    <div
                      style={{
                        color: cat.bicycle < cat.transit
                          ? "#66bb6a"
                          : "#ef5350",
                      }}
                    >
                      {cat.bicycle} min
                    </div>
                  </div>
                  <div style={{ textAlign: "center" }}>
                    <div style={{ fontSize: "11px", color: "#888" }}>
                      Marche
                    </div>
                    <div style={{ color: "#ffa726" }}>{cat.walk} min</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
