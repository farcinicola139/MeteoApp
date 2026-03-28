
# Meteo App 🌤️

Applicazione Python modulare per il meteo, con CLI, API REST (FastAPI) e interfaccia web.

## Funzionalità

- 🌡️ **Meteo corrente**: temperatura (°C/°F), umidità, vento, precipitazioni
- 📅 **Previsioni 5 giorni**: min/max temperatura, umidità, vento, pioggia
- 🏙️ **Multi-città**: inserisci più città separate da virgola
- 📍 **Geolocalizzazione**: rilevamento automatico della posizione tramite browser
- 🔭 **Astronomia**: pianeti visibili, fase lunare, eventi astronomici (attivabile/disattivabile)
- 🌙 **Tema Light/Dark**: toggle con preferenza salvata
- ❤️ **Preferiti**: sidebar con città salvate in localStorage
- ⚡ **Cache intelligente**: dati salvati per 1 ora (file JSON)
- 🚀 **Chiamate parallele**: fetch simultaneo per più città
- 🌐 **API REST**: backend FastAPI con endpoint JSON
- 💻 **Frontend web**: interfaccia HTML/CSS/JS moderna e responsive

## Struttura progetto

```
meteo_app/
├── main.py                  # CLI entry point
├── requirements.txt
├── README.md
├── meteo/
│   ├── __init__.py          # Package exports
│   ├── exceptions.py        # Eccezioni personalizzate
│   ├── cache.py             # Cache JSON con scadenza (TTL 1h)
│   ├── weather.py           # API calls (geocoding + meteo + forecast + reverse geocoding)
│   ├── astronomy.py         # Calcoli astronomici (PyEphem) — pianeti, luna, eventi
│   ├── formatter.py         # Formattazione output terminale
│   ├── api.py               # Backend REST (FastAPI)
│   └── app.py               # Retrocompatibilità (deprecato)
├── frontend/
│   ├── index.html           # Interfaccia web (geoloc, astronomia, tema light/dark)
│   └── style.css            # Stili con CSS variables per Light/Dark mode
└── tests/
    ├── __init__.py
    └── test_app.py           # Test suite (30+ test)
```

## Installazione

```bash
pip install -r requirements.txt
```

### Dipendenze

| Pacchetto | Uso |
|---|---|
| `requests` | Chiamate HTTP alle API meteo/geocoding |
| `fastapi` | Backend REST API |
| `uvicorn` | Server ASGI |
| `ephem` | Calcoli astronomici offline (pianeti, luna, eventi) |

## Utilizzo

### CLI (terminale)

```bash
python main.py
```

Esempio:
```
Inserisci una o più città (separate da virgola): Roma, Milano, Napoli

🔍 Recupero dati meteo per: Roma, Milano, Napoli...

Città              °C     °F  Umid.    Vento  Pioggia
────────────────────────────────────────────────────────
Roma              22.5   72.5    65%  12 km/h   0.0 mm
Milano            18.3   64.9    72%   8 km/h   1.2 mm
Napoli            20.1   68.2    68%  15 km/h   0.0 mm
```

### Web (frontend + API)

```bash
uvicorn meteo.api:app --reload --port 8000
```

Poi apri http://localhost:8000 nel browser.

#### Funzionalità interfaccia web

- **Barra di ricerca**: inserisci città e premi Cerca
- **📍 Posizione**: pulsante per geolocalizzazione automatica (richiede permesso browser)
- **🔭 Astronomia**: toggle per attivare/disattivare la sezione astronomica sotto ogni città
- **🌙/☀️ Tema**: pulsante in alto a destra per switch Light/Dark mode
- **❤️ Preferiti**: sidebar con città salvate, aggiornamento automatico dati
- **Geolocalizzazione automatica**: all'apertura dell'app tenta di mostrare il meteo della posizione corrente

### API REST

| Endpoint | Descrizione |
|---|---|
| `GET /api/weather?city=Roma` | Meteo singola città |
| `GET /api/weather?city=Roma,Milano` | Multi-città |
| `GET /api/weather?city=Roma&days=3` | Previsioni personalizzate |
| `GET /api/weather/coords?lat=41.89&lon=12.51` | Meteo per coordinate GPS (geolocalizzazione) |
| `GET /api/astronomy?lat=41.89&lon=12.51` | Dati astronomici per posizione |
| `GET /api/cache/clear` | Svuota cache |
| `GET /docs` | Documentazione Swagger auto-generata |

#### Esempio risposta `/api/astronomy`

```json
{
  "planets_visible": [
    {
      "name": "Giove",
      "emoji": "♃",
      "altitude_deg": 49.1,
      "magnitude": -2.1,
      "rise_time": "08:59 UTC",
      "set_time": "00:51 UTC",
      "constellation": "Gemini",
      "visible": true
    }
  ],
  "visible_count": 2,
  "moon": {
    "phase_pct": 81.2,
    "phase_name": "Gibbosa crescente",
    "emoji": "🌔",
    "next_full_moon": "2026-04-02",
    "next_new_moon": "2026-04-17"
  },
  "sun": {
    "sunrise": "03:58 UTC",
    "sunset": "16:39 UTC"
  },
  "events": [
    { "date": "2026-04-02", "event": "Luna piena 🌕", "type": "lunar" },
    { "date": "2026-04-15", "event": "Congiunzione Marte-Saturno 🌟 (2.9°)", "type": "conjunction" },
    { "date": "2026-04-22", "event": "Liridi ☄️", "type": "meteor_shower" }
  ]
}
```

## Sezione Astronomia 🔭

La sezione astronomica utilizza la libreria **PyEphem** per calcoli offline (nessuna API key necessaria):

- **Pianeti visibili**: quali pianeti sono sopra l'orizzonte, con altitudine, magnitudine, costellazione e orari levata/tramonto
- **Fase lunare**: percentuale illuminazione, nome fase, prossime fasi principali
- **Alba/Tramonto sole**: orari calcolati per la posizione
- **Prossimi eventi**: fasi lunari, sciami meteorici (Perseidi, Geminidi, ecc.), congiunzioni planetarie

L'utente può attivare/disattivare questa sezione tramite il toggle "🔭 Astronomia" nell'interfaccia. La preferenza viene salvata in localStorage.

## Test

```bash
python -m pytest tests/ -v
```

### Casi di test coperti (30+)

| Scenario | Test |
|---|---|
| Conversione °C → °F | Zero, positivi, negativi, decimali, tipo errato |
| Città valida | Coordinate corrette, nome ufficiale |
| Città inesistente | CityNotFoundError, nessuna chiamata meteo |
| Input vuoto/invalido | ValueError per stringhe vuote, spazi, non-stringa |
| Errori API | Timeout, connessione, HTTP 500/503 |
| JSON malformato | JSONDecodeError gestito con eccezione chiara |
| Dati mancanti | Chiavi assenti nella risposta API |
| Cache | Set/get, scadenza TTL, persistenza disco, cleanup |
| Formattazione | Output contiene città, temperature, previsioni |
| Multi-città | Risultati paralleli, errori parziali |

## Architettura

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  Frontend    │────▶│  FastAPI      │────▶│  weather.py     │
│  (HTML/JS)  │     │  (api.py)     │     │  (API calls)    │
└─────────────┘     └──────────────┘     └────────┬────────┘
       │                    │                      │
       │                    │              ┌───────▼────────┐
       │                    │              │  cache.py      │
       │                    │              │  (JSON + TTL)  │
       │                    │              └────────────────┘
       │                    │
       │              ┌─────▼──────────┐
       │              │  astronomy.py  │
       │              │  (PyEphem)     │
       │              └────────────────┘
       │
┌──────▼──────┐
│  Browser    │
│  Geoloc API │
└─────────────┘

┌─────────────┐
│  CLI         │──────────────────────────▶  weather.py
│  (main.py)   │
└─────────────┘
```

## Sicurezza 🔒

| Misura | Descrizione |
|---|---|
| ✅ **Nessuna API key** | Nessun segreto nel codice. Tutte le API sono gratuite e senza chiave |
| ✅ **XSS protection** | Funzioni `esc()` e `escJs()` per escape HTML e JS nei contenuti dinamici |
| ✅ **Input validation** | Limite 500 caratteri, max 10 città per richiesta, validazione coordinate |
| ✅ **Error sanitization** | I messaggi HTTP 500 non espongono dettagli interni (stacktrace, percorsi) |
| ✅ **CORS ristretto** | Solo metodi `GET` ammessi; in produzione restringere `allow_origins` |
| ✅ **Thread-safe cache** | `threading.Lock` su tutte le operazioni cache (usata con ThreadPoolExecutor) |

> **Nota**: CORS è impostato su `allow_origins=["*"]` per lo sviluppo locale. In produzione, sostituire con il dominio specifico del frontend.

## API e librerie utilizzate

| Servizio | URL / Libreria | Uso | API Key |
|---|---|---|---|
| Open-Meteo Geocoding | `geocoding-api.open-meteo.com` | Nome città → coordinate | ❌ No |
| Open-Meteo Forecast | `api.open-meteo.com` | Dati meteo correnti e previsioni | ❌ No |
| Nominatim (OpenStreetMap) | `nominatim.openstreetmap.org` | Reverse geocoding (coordinate → nome) | ❌ No |
| PyEphem | `pip install ephem` | Calcoli astronomici offline | ❌ No |
| Browser Geolocation API | `navigator.geolocation` | Posizione GPS dell'utente | Permesso browser |
=======


