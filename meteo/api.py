"""Backend REST API con FastAPI per l'applicazione meteo.

Endpoint:
    GET  /api/weather?city=Roma             → Meteo singola città
    GET  /api/weather?city=Roma,Milano      → Meteo multi-città
    GET  /api/weather?city=Roma&days=3      → Previsioni personalizzate
    GET  /api/weather/coords?lat=..&lon=..  → Meteo per coordinate (geolocalizzazione)
    GET  /api/astronomy?lat=..&lon=..       → Dati astronomici per posizione
    GET  /api/cache/clear                   → Svuota la cache

Avvio:
    uvicorn meteo.api:app --reload --port 8000

Oppure:
    python -m meteo.api
"""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from meteo.exceptions import CityNotFoundError, GeocodingAPIError, WeatherAPIError
from meteo.weather import fetch_multiple_cities, fetch_weather_by_coords, get_cache
from meteo.astronomy import get_astronomy_data

logger = logging.getLogger(__name__)

# ── App FastAPI ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="Meteo App API",
    description="API REST per dati meteo correnti e previsioni multi-giorno.",
    version="2.0.0",
)

# CORS: in sviluppo consenti tutto; in produzione restringere a domini specifici
# Esempio produzione: allow_origins=["https://miodominio.it"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# ── Costanti sicurezza ────────────────────────────────────────────────────────
MAX_CITY_INPUT_LENGTH = 500  # Lunghezza massima stringa città
MAX_CITIES_PER_REQUEST = 10  # Massimo città per singola richiesta


# ── Serve frontend statico ───────────────────────────────────────────────────
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")

if os.path.isdir(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/", include_in_schema=False)
    async def serve_frontend():
        """Serve la pagina principale del frontend."""
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


# ── Endpoint meteo ────────────────────────────────────────────────────────────


@app.get("/api/weather")
async def get_weather_endpoint(
    city: str = Query(..., description="Nome città (o lista separata da virgola)"),
    days: int = Query(5, ge=1, le=16, description="Giorni di previsione (1-16)"),
    cache: bool = Query(True, description="Usa la cache (default: true)"),
):
    """Recupera i dati meteo per una o più città.

    Args:
        city: Nome della città o lista separata da virgola (es. "Roma,Milano").
        days: Numero di giorni di previsione (1-16, default 5).
        cache: Se usare la cache (default True).

    Returns:
        JSONResponse con i dati meteo per ogni città.

    Raises:
        HTTPException 400: Se nessuna città valida è specificata.
        HTTPException 404: Se nessuna città viene trovata.
        HTTPException 502: Se le API esterne non sono raggiungibili.
    """
    # Validazione input
    if len(city) > MAX_CITY_INPUT_LENGTH:
        raise HTTPException(status_code=400, detail="Input troppo lungo. Massimo 500 caratteri.")

    # Parsing città
    cities = [c.strip() for c in city.split(",") if c.strip()]
    if not cities:
        raise HTTPException(status_code=400, detail="Specifica almeno una città.")
    if len(cities) > MAX_CITIES_PER_REQUEST:
        raise HTTPException(status_code=400, detail=f"Massimo {MAX_CITIES_PER_REQUEST} città per richiesta.")

    try:
        results = fetch_multiple_cities(cities, forecast_days=days, use_cache=cache)
    except Exception as e:
        logger.exception("Errore imprevisto in fetch_multiple_cities")
        raise HTTPException(status_code=500, detail="Errore interno del server.")

    # Controlla se tutte le città hanno errori
    errors = [r for r in results if "error" in r]
    if len(errors) == len(results):
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Nessuna città trovata.",
                "errors": [{"city": e["city"], "error": e["error"]} for e in errors],
            },
        )

    return JSONResponse(
        content={
            "count": len(results),
            "results": results,
        }
    )


# ── Endpoint meteo per coordinate (geolocalizzazione) ─────────────────────────


def _validate_coords(lat: float, lon: float) -> None:
    """Valida coordinate geografiche.

    Raises:
        HTTPException 400: Se le coordinate sono fuori range.
    """
    if not (-90 <= lat <= 90):
        raise HTTPException(status_code=400, detail=f"Latitudine non valida: {lat}. Deve essere tra -90 e 90.")
    if not (-180 <= lon <= 180):
        raise HTTPException(status_code=400, detail=f"Longitudine non valida: {lon}. Deve essere tra -180 e 180.")


@app.get("/api/weather/coords")
async def get_weather_by_coords_endpoint(
    lat: float = Query(..., description="Latitudine (-90..90)"),
    lon: float = Query(..., description="Longitudine (-180..180)"),
    days: int = Query(5, ge=1, le=16, description="Giorni di previsione (1-16)"),
):
    """Recupera i dati meteo a partire dalle coordinate GPS.

    Usato dalla funzione di geolocalizzazione del browser.
    Esegue reverse geocoding per ottenere il nome della località.

    Args:
        lat: Latitudine in gradi decimali (-90..90).
        lon: Longitudine in gradi decimali (-180..180).
        days: Numero di giorni di previsione (1-16, default 5).

    Returns:
        JSONResponse con i dati meteo per la posizione.
    """
    _validate_coords(lat, lon)
    try:
        result = fetch_weather_by_coords(lat, lon, forecast_days=days)
        return JSONResponse(
            content={
                "count": 1,
                "results": [result],
            }
        )
    except WeatherAPIError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.exception("Errore in fetch_weather_by_coords")
        raise HTTPException(status_code=500, detail="Errore interno del server.")


# ── Endpoint astronomia ──────────────────────────────────────────────────────


@app.get("/api/astronomy")
async def get_astronomy_endpoint(
    lat: float = Query(..., description="Latitudine (-90..90)"),
    lon: float = Query(..., description="Longitudine (-180..180)"),
):
    """Restituisce dati astronomici per la posizione specificata.

    Include: pianeti visibili, fase lunare, alba/tramonto, eventi.

    Args:
        lat: Latitudine in gradi decimali (-90..90).
        lon: Longitudine in gradi decimali (-180..180).

    Returns:
        JSONResponse con i dati astronomici completi.
    """
    _validate_coords(lat, lon)
    try:
        data = get_astronomy_data(lat, lon)
        return JSONResponse(content=data)
    except Exception as e:
        logger.exception("Errore in get_astronomy_data")
        raise HTTPException(status_code=500, detail="Errore nei calcoli astronomici.")


# ── Cache ─────────────────────────────────────────────────────────────────────


@app.get("/api/cache/clear")
async def clear_cache():
    """Svuota la cache dei dati meteo.

    Returns:
        Messaggio di conferma.
    """
    cache = get_cache()
    cache.clear()
    return {"message": "Cache svuotata con successo."}


# ── Avvio diretto ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("meteo.api:app", host="0.0.0.0", port=8000, reload=True)
