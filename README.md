# TransitScope

**Tableau de bord d'accessibilité multi-modale configurable par ville**

TransitScope visualise, pour n'importe quel point d'une ville, combien de services (santé, alimentation, transport) sont accessibles en transports en commun, à vélo ou à pied — selon l'heure réelle de la journée. Les perturbations GTFS-RT sont intégrées en temps réel.

> Projet de portfolio — développeur SIG full-stack · Python · C# / ASP.NET Core · TypeScript

---

## Aperçu

![Capture d'écran de la carte interactive](docs/screenshot.png)

L'utilisateur sélectionne une ville, un point d'origine sur la carte et une heure. TransitScope calcule les isochrones pour les trois modes de transport et affiche le nombre de points d'intérêt atteignables. Un panneau latéral compare les modes et détecte les inégalités d'accès selon les quartiers.

---

## Fonctionnalités

- **Isochrones dynamiques** — calculés par `r5py` (moteur R5/OpenTripPlanner) à partir des horaires GTFS réels
- **Trois modes simultanés** — transports en commun, vélo (réseau OSM), marche à pied
- **Slider horaire** — de 6h à 23h, par tranches de 30 minutes; les isochrones se recalculent à la volée
- **Alertes temps réel** — perturbations et retards GTFS-RT poussés via WebSocket toutes les 30 secondes
- **Multi-ville** — configuration par fichier YAML; deux villes incluses par défaut (Montréal, Rennes)
- **Trois catégories de POI** — santé, alimentation, mobilité (données OpenStreetMap)
- **Panel d'inégalités** — comparaison de l'accessibilité par quartier, croisée avec les données du recensement

---

## Architecture

```
transitscope/
├── ingestion/          # Python — ETL GTFS, OSM, StatCan
├── analysis/           # Python — calcul isochrones (r5py, GeoPandas, OSMnx)
├── api/                # C# ASP.NET Core — REST + WebSocket (SignalR)
├── frontend/           # TypeScript / React — carte Deck.gl + MapLibre GL
├── db/                 # Migrations PostGIS (Flyway)
├── config/
│   └── cities/         # Un fichier YAML par ville configurée
└── docs/
```

### Flux d'une requête isochrone

```
Utilisateur (slider) → API C# → vérification Redis
                                  ├── cache hit  → GeoJSON → carte
                                  └── cache miss → r5py → PostGIS (POI) → Redis → carte
```

### Pourquoi ce stack ?

| Couche | Technologie | Justification |
|---|---|---|
| Calcul géospatial | Python · r5py · GeoPandas · OSMnx | Écosystème géomatique sans équivalent; r5py est le seul moteur multimodal open source mature |
| API | C# · ASP.NET Core · SignalR | WebSocket natif via SignalR, cache Redis clé-en-main, Swagger automatique — standard enterprise |
| Frontend | TypeScript · React · Deck.gl · MapLibre GL | Bibliothèques cartographiques web TypeScript-first; performances GPU pour les couches vectorielles |
| Stockage | PostgreSQL · PostGIS | Calculs spatiaux côté base (ST_Within, ST_Intersects), indexation GIST sur les géométries |
| Temps réel | GTFS-RT (protobuf) · Celery · Redis Pub/Sub | Ingestion asynchrone des flux d'agences; diffusion découplée vers les clients WebSocket |

---

## Données

| Source | Format | Fréquence de mise à jour |
|---|---|---|
| Horaires TC | GTFS statique (.zip) | Hebdomadaire (selon l'agence) |
| Perturbations | GTFS-RT (protobuf) | Toutes les 30 secondes |
| Réseau routier / cyclable | OpenStreetMap (PBF) | Mensuelle |
| Points d'intérêt | OpenStreetMap (Overpass API) | Mensuelle |
| Données socioéconomiques | Statistique Canada — recensement 2021 | Ponctuelle |

### Villes configurées

| Ville | Agence TC | Statut |
|---|---|---|
| Montréal | STM | actif |
| Rennes | STAR | actif |

Ajouter une ville : copier `config/cities/template.yaml`, renseigner les URLs GTFS et l'emprise géographique.

---

## Installation

### Prérequis

- Docker et Docker Compose
- Python 3.11+
- .NET 8 SDK
- Node.js 20+

### Démarrage rapide

```bash
# Cloner le dépôt
git clone https://github.com/votre-pseudo/transitscope.git
cd transitscope

# Copier et compléter les variables d'environnement
cp .env.example .env

# Lancer les services (PostGIS, Redis, API, frontend)
docker compose up -d

# Initialiser une ville (télécharge GTFS + OSM, construit le graphe r5py)
python ingestion/bootstrap_city.py --city montreal

# L'application est accessible sur http://localhost:3000
```

### Variables d'environnement requises

```env
POSTGRES_CONNECTION=Host=localhost;Database=transitscope;Username=...;Password=...
REDIS_URL=redis://localhost:6379
MAPLIBRE_STYLE_URL=https://...   # Fond de carte (ex. MapTiler, Stadia)
```

---

## Structure du projet (détail)

### `ingestion/` — Python

- `gtfs_loader.py` — téléchargement, validation et chargement GTFS statique via `gtfs-kit`
- `gtfs_rt_consumer.py` — décodage protobuf GTFS-RT, publication Redis Pub/Sub
- `osm_loader.py` — extraction POI et réseau via Overpass + OSMnx
- `census_loader.py` — import des données de recensement StatCan (CSV → PostGIS)
- `tasks.py` — tâches Celery planifiées (refresh GTFS-RT, mise à jour OSM mensuelle)

### `analysis/` — Python

- `isochrone.py` — calcul r5py multimodal, export GeoJSON, écriture cache Redis
- `accessibility.py` — comptage POI dans les isochrones (ST_Within via GeoPandas + PostGIS)
- `inequality.py` — agrégation par quartier, indice d'accessibilité composite

### `api/` — C# ASP.NET Core

- `Controllers/IsochroneController.cs` — endpoint REST `/api/isochrone`
- `Controllers/CityController.cs` — liste et configuration des villes disponibles
- `Hubs/AlertHub.cs` — SignalR hub, diffusion des alertes GTFS-RT
- `Services/CacheService.cs` — abstraction Redis (lecture/écriture isochrones)
- `Services/PythonBridge.cs` — appel des micro-services Python via HTTP interne

### `frontend/` — TypeScript / React

- `components/Map.tsx` — carte MapLibre GL + couches Deck.gl (isochrones, POI, alertes)
- `components/TimeSlider.tsx` — contrôle horaire, déclenchement des requêtes
- `components/SidePanel.tsx` — statistiques d'accessibilité, comparaison des modes
- `hooks/useIsochrone.ts` — fetch + cache côté client
- `hooks/useAlerts.ts` — connexion SignalR, gestion des alertes temps réel

---

## Roadmap

- [x] ETL GTFS statique + OSM
- [x] Calcul isochrones mono-modal (TC)
- [x] API REST isochrones avec cache Redis
- [x] Frontend carte + slider horaire
- [ ] Modes vélo et marche (r5py multimodal)
- [ ] Intégration GTFS-RT + WebSocket
- [ ] Panel inégalités (données recensement)
- [ ] Support multi-ville (config YAML)
- [ ] Déploiement Fly.io / Railway

---

## Références

- Conveyal R5 / r5py — moteur de calcul d'accessibilité multimodale
- OpenTripPlanner — alternative open source pour le routage TC
- Levinson, D. et al. (2020). *Transport Access Manual*. University of Sydney.
- El-Geneidy, A. et al. (2016). The cost of equity: Assessing transit accessibility and social disparity using total travel cost. *Transportation Research Part A*.
- Boisjoly, G. & El-Geneidy, A. (2017). How to get there? A critical assessment of accessibility objectives and indicators in metropolitan transportation plans. *Transport Policy*.

---

## Licence

MIT — voir `LICENSE`
