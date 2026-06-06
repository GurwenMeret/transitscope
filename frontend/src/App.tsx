import { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import "./App.css";

const API_URL = "http://localhost:5062";

const MODE_COLORS: Record<string, string> = {
  transit: "#7c4dff",
  bicycle: "#00c853",
  walk: "#ff6d00",
};

const MODE_LABELS: Record<string, string> = {
  transit: "Transport en commun",
  bicycle: "Vélo",
  walk: "Marche",
};

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
  const marker = useRef<maplibregl.Marker | null>(null);
  const [time, setTime] = useState("08:00");
  const [itineraries, setItineraries] = useState<Itinerary[]>([]);
  const [accessibility, setAccessibility] = useState<AccessibilityCategory[]>(
    [],
  );
  const [loading, setLoading] = useState(false);
  const [selectedPoint, setSelectedPoint] = useState<
    { lat: number; lon: number } | null
  >(null);
  const [visibleModes, setVisibleModes] = useState<Record<string, boolean>>({
    transit: true,
    bicycle: true,
    walk: true,
  });

  useEffect(() => {
    if (map.current || !mapContainer.current) return;

    map.current = new maplibregl.Map({
      container: mapContainer.current,
      style: "https://tiles.openfreemap.org/styles/liberty",
      center: [-73.5690, 45.5088],
      zoom: 12,
    });

    map.current.addControl(new maplibregl.NavigationControl());

    map.current.on("load", () => {
      // Ajouter les sources et couches pour chaque mode
      for (const mode of ["transit", "bicycle", "walk"]) {
        map.current!.addSource(`isochrone-${mode}`, {
          type: "geojson",
          data: { type: "FeatureCollection", features: [] },
        });

        map.current!.addLayer({
          id: `isochrone-${mode}-fill`,
          type: "fill",
          source: `isochrone-${mode}`,
          paint: {
            "fill-color": MODE_COLORS[mode],
            "fill-opacity": 0.2,
          },
        });

        map.current!.addLayer({
          id: `isochrone-${mode}-outline`,
          type: "line",
          source: `isochrone-${mode}`,
          paint: {
            "line-color": MODE_COLORS[mode],
            "line-width": 2,
            "line-opacity": 0.8,
          },
        });
      }
    });

    map.current.on("click", async (e) => {
      const { lat, lng: lon } = e.lngLat;
      setSelectedPoint({ lat, lon });
      setLoading(true);

      // Marqueur au point cliqué
      if (marker.current) marker.current.remove();
      marker.current = new maplibregl.Marker({ color: "#ff1744" })
        .setLngLat([lon, lat])
        .addTo(map.current!);

      const hour = parseInt(time.split(":")[0]);

      try {
        const [isoRes, accRes, polygonRes] = await Promise.all([
          fetch(
            `${API_URL}/api/isochrone?lat=${lat}&lon=${lon}&time=${time}:00&maxMinutes=30`,
          ),
          fetch(
            `${API_URL}/api/accessibility?lat=${lat}&lon=${lon}&city=montreal&time=${time}:00`,
          ),
          fetch(
            `${API_URL}/api/isochrones/nearest?lat=${lat}&lon=${lon}&hour=${hour}&maxMinutes=30`,
          ),
        ]);

        const isoData = await isoRes.json();
        const accData = await accRes.json();
        const polygonData = await polygonRes.json();

        setItineraries(isoData?.data?.plan?.itineraries ?? []);
        setAccessibility(accData?.categories ?? []);

        // Mettre à jour les polygones sur la carte
        for (const feature of polygonData.features) {
          const mode = feature.properties.mode;
          const source = map.current!.getSource(
            `isochrone-${mode}`,
          ) as maplibregl.GeoJSONSource;
          if (source) {
            source.setData({
              type: "FeatureCollection",
              features: [feature],
            });
          }
        }
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    });
  }, []);

  const toggleMode = (mode: string) => {
    const newVisible = { ...visibleModes, [mode]: !visibleModes[mode] };
    setVisibleModes(newVisible);

    if (map.current) {
      const visibility = newVisible[mode] ? "visible" : "none";
      map.current.setLayoutProperty(
        `isochrone-${mode}-fill`,
        "visibility",
        visibility,
      );
      map.current.setLayoutProperty(
        `isochrone-${mode}-outline`,
        "visibility",
        visibility,
      );
    }
  };

  return (
    <div style={{ display: "flex", height: "100vh", width: "100vw" }}>
      <div ref={mapContainer} style={{ flex: 1 }} />

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

        {/* Toggle modes */}
        <div style={{ marginBottom: "20px" }}>
          <p style={{ fontSize: "13px", color: "#aaa", marginBottom: "8px" }}>
            Isochrones visibles :
          </p>
          {Object.entries(MODE_LABELS).map(([mode, label]) => (
            <button
              key={mode}
              onClick={() => toggleMode(mode)}
              style={{
                display: "block",
                width: "100%",
                marginBottom: "6px",
                padding: "8px 12px",
                background: visibleModes[mode]
                  ? MODE_COLORS[mode] + "33"
                  : "#333",
                border: `2px solid ${
                  visibleModes[mode] ? MODE_COLORS[mode] : "#555"
                }`,
                borderRadius: "6px",
                color: visibleModes[mode] ? MODE_COLORS[mode] : "#888",
                cursor: "pointer",
                fontSize: "13px",
                textAlign: "left",
              }}
            >
              ● {label}
            </button>
          ))}
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
