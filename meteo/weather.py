"""Modulo per le chiamate API meteo e geocoding.

Gestisce:
- Geocoding (nome città → coordinate)
- Meteo corrente (temperatura, umidità, vento, precipitazioni)
- Previsioni multi-giorno (5 giorni, min/max temperatura)
- Chiamate parallele per più città
- Integrazione con il sistema di cache

API utilizzate (Open-Meteo, gratuite, no API key):
- Geocoding: https://geocoding-api.open-meteo.com/v1/search
- Forecast:  https://api.open-meteo.com/v1/forecast
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any

import requests

from meteo.cache import WeatherCache
from meteo.exceptions import CityNotFoundError, GeocodingAPIError, WeatherAPIError

# ── Costanti API ──────────────────────────────────────────────────────────────
GEOCODING_URL: str = "https://geocoding-api.open-meteo.com/v1/search"
REVERSE_GEOCODING_URL: str = "https://nominatim.openstreetmap.org/reverse"
WEATHER_URL: str = "https://api.open-meteo.com/v1/forecast"
REQUEST_TIMEOUT: int = 10
MAX_PARALLEL_WORKERS: int = 5

# ── Cache globale (singleton) ────────────────────────────────────────────────
_cache = WeatherCache()


def get_cache() -> WeatherCache:
    """Restituisce l'istanza globale della cache.

    Returns:
        L'istanza WeatherCache condivisa dall'applicazione.
    """
    return _cache


# ── Geocoding ─────────────────────────────────────────────────────────────────


def get_coordinates(city: str) -> tuple[float, float, str]:
    """Recupera latitudine, longitudine e nome ufficiale della città.

    Utilizza l'API di geocoding di Open-Meteo per convertire il nome
    di una città nelle sue coordinate geografiche.

    Args:
        city: Nome della città da cercare (case-insensitive).

    Returns:
        Tupla (latitudine, longitudine, nome_ufficiale_città).

    Raises:
        ValueError: Se il nome della città è vuoto o non è una stringa.
        CityNotFoundError: Se la città non viene trovata nell'API.
        GeocodingAPIError: Per errori di connessione, timeout o HTTP.

    Example:
        >>> lat, lon, name = get_coordinates("roma")
        >>> print(f"{name}: {lat}, {lon}")
        Roma: 41.89193, 12.51133
    """
    if not isinstance(city, str) or not city.strip():
        raise ValueError("Il nome della città non può essere vuoto.")

    params = {"name": city.strip(), "count": 1}

    try:
        response = requests.get(GEOCODING_URL, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
    except requests.ConnectionError:
        raise GeocodingAPIError(
            "Errore di connessione: impossibile raggiungere l'API di geocoding."
        )
    except requests.Timeout:
        raise GeocodingAPIError(
            "Errore: timeout nella richiesta all'API di geocoding."
        )
    except requests.HTTPError as e:
        status = getattr(e.response, "status_code", "sconosciuto")
        raise GeocodingAPIError(f"Errore HTTP dall'API di geocoding: {status}")
    except requests.RequestException as e:
        raise GeocodingAPIError(f"Errore imprevisto nell'API di geocoding: {e}")

    try:
        data = response.json()
    except (json.JSONDecodeError, ValueError):
        raise GeocodingAPIError("Errore: risposta non valida dall'API di geocoding.")

    if "results" not in data or len(data["results"]) == 0:
        raise CityNotFoundError(city.strip())

    result = data["results"][0]
    return result["latitude"], result["longitude"], result["name"]


# ── Reverse Geocoding ─────────────────────────────────────────────────────────


def reverse_geocode(lat: float, lon: float) -> str:
    """Converte coordinate geografiche in nome della località.

    Utilizza l'API Nominatim di OpenStreetMap (gratuita, no API key).

    Args:
        lat: Latitudine in gradi decimali.
        lon: Longitudine in gradi decimali.

    Returns:
        Nome della località (città/comune) o fallback "lat, lon".
    """
    params = {
        "lat": lat,
        "lon": lon,
        "format": "json",
        "zoom": 10,
        "addressdetails": 1,
    }
    headers = {"User-Agent": "MeteoApp/2.0"}

    try:
        response = requests.get(
            REVERSE_GEOCODING_URL, params=params, headers=headers, timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        data = response.json()

        address = data.get("address", {})
        # Prova diversi campi per ottenere il nome più utile
        name = (
            address.get("city")
            or address.get("town")
            or address.get("village")
            or address.get("municipality")
            or address.get("county")
            or data.get("display_name", "").split(",")[0]
        )
        return name if name else f"{lat}, {lon}"
    except Exception:
        return f"{lat}, {lon}"


# ── Fetch meteo per coordinate (senza geocoding diretto) ─────────────────────


def fetch_weather_by_coords(
    lat: float, lon: float, forecast_days: int = 5
) -> dict[str, Any]:
    """Recupera i dati meteo direttamente dalle coordinate.

    Usato per la geolocalizzazione browser: riceve lat/lon,
    fa reverse geocoding per il nome e poi chiama l'API meteo.

    Args:
        lat: Latitudine.
        lon: Longitudine.
        forecast_days: Giorni di previsione (1-16, default 5).

    Returns:
        Dizionario completo con info località e dati meteo.
    """
    # Reverse geocoding per ottenere il nome della località
    city_name = reverse_geocode(lat, lon)

    # Meteo
    weather = get_weather(lat, lon, forecast_days=forecast_days)

    return {
        "city": city_name,
        "latitude": round(lat, 4),
        "longitude": round(lon, 4),
        "cached": False,
        "geolocated": True,
        "current": weather["current"],
        "forecast": weather["forecast"],
    }


# ── Meteo corrente + previsioni ───────────────────────────────────────────────


def get_weather(lat: float, lon: float, forecast_days: int = 5) -> dict[str, Any]:
    """Recupera meteo corrente e previsioni multi-giorno per le coordinate date.

    Restituisce una struttura dati completa con:
    - Meteo corrente: temperatura, umidità, vento, precipitazioni
    - Previsioni giornaliere: min/max temperatura, umidità, vento, precipitazioni

    Args:
        lat: Latitudine (es. 41.89).
        lon: Longitudine (es. 12.51).
        forecast_days: Numero di giorni di previsione (1-16, default 5).

    Returns:
        Dizionario strutturato con chiavi 'current' e 'forecast'.
        Esempio::

            {
                "current": {
                    "temperature_c": 22.5,
                    "temperature_f": 72.5,
                    "humidity": 65,
                    "wind_speed_kmh": 12.3,
                    "precipitation_mm": 0.0
                },
                "forecast": [
                    {
                        "date": "2026-03-28",
                        "date_readable": "Sabato 28 Marzo 2026",
                        "temp_min_c": 14.2,
                        "temp_max_c": 24.1,
                        "temp_min_f": 57.6,
                        "temp_max_f": 75.4,
                        "humidity_mean": 58,
                        "wind_speed_max_kmh": 18.5,
                        "precipitation_sum_mm": 0.0
                    },
                    ...
                ]
            }

    Raises:
        WeatherAPIError: Per errori di connessione, timeout, HTTP o dati mancanti.

    Example:
        >>> weather = get_weather(41.89, 12.51, forecast_days=3)
        >>> print(weather["current"]["temperature_c"])
        22.5
    """
    forecast_days = max(1, min(forecast_days, 16))

    params = {
        "latitude": lat,
        "longitude": lon,
        # Dati correnti
        "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation",
        # Previsioni giornaliere
        "daily": (
            "temperature_2m_max,temperature_2m_min,"
            "relative_humidity_2m_max,relative_humidity_2m_min,"
            "wind_speed_10m_max,precipitation_sum"
        ),
        "forecast_days": forecast_days,
        "timezone": "auto",
    }

    try:
        response = requests.get(WEATHER_URL, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
    except requests.ConnectionError:
        raise WeatherAPIError(
            "Errore di connessione: impossibile raggiungere l'API meteo."
        )
    except requests.Timeout:
        raise WeatherAPIError("Errore: timeout nella richiesta all'API meteo.")
    except requests.HTTPError as e:
        status = getattr(e.response, "status_code", "sconosciuto")
        raise WeatherAPIError(f"Errore HTTP dall'API meteo: {status}")
    except requests.RequestException as e:
        raise WeatherAPIError(f"Errore imprevisto nell'API meteo: {e}")

    try:
        data = response.json()
    except (json.JSONDecodeError, ValueError):
        raise WeatherAPIError("Errore: risposta non valida dall'API meteo.")

    # ── Parsing dati correnti ──
    current_raw = data.get("current")
    if current_raw is None:
        raise WeatherAPIError("Errore: dati meteo correnti non disponibili.")

    temp_c = current_raw.get("temperature_2m", 0.0)
    current = {
        "temperature_c": temp_c,
        "temperature_f": celsius_to_fahrenheit(temp_c),
        "humidity": current_raw.get("relative_humidity_2m", 0),
        "wind_speed_kmh": current_raw.get("wind_speed_10m", 0.0),
        "precipitation_mm": current_raw.get("precipitation", 0.0),
    }

    # ── Parsing previsioni giornaliere ──
    daily_raw = data.get("daily", {})
    dates = daily_raw.get("time", [])
    temp_maxs = daily_raw.get("temperature_2m_max", [])
    temp_mins = daily_raw.get("temperature_2m_min", [])
    hum_maxs = daily_raw.get("relative_humidity_2m_max", [])
    hum_mins = daily_raw.get("relative_humidity_2m_min", [])
    wind_maxs = daily_raw.get("wind_speed_10m_max", [])
    precip_sums = daily_raw.get("precipitation_sum", [])

    forecast = []
    for i, date_str in enumerate(dates):
        t_min = temp_mins[i] if i < len(temp_mins) else 0.0
        t_max = temp_maxs[i] if i < len(temp_maxs) else 0.0
        h_max = hum_maxs[i] if i < len(hum_maxs) else 0
        h_min = hum_mins[i] if i < len(hum_mins) else 0
        forecast.append({
            "date": date_str,
            "date_readable": _format_date(date_str),
            "temp_min_c": t_min,
            "temp_max_c": t_max,
            "temp_min_f": celsius_to_fahrenheit(t_min),
            "temp_max_f": celsius_to_fahrenheit(t_max),
            "humidity_mean": round((h_max + h_min) / 2) if (h_max + h_min) else 0,
            "wind_speed_max_kmh": wind_maxs[i] if i < len(wind_maxs) else 0.0,
            "precipitation_sum_mm": precip_sums[i] if i < len(precip_sums) else 0.0,
        })

    return {"current": current, "forecast": forecast}


# ── Fetch completo per una città (con cache) ─────────────────────────────────


def fetch_city_weather(
    city: str, forecast_days: int = 5, use_cache: bool = True
) -> dict[str, Any]:
    """Recupera tutti i dati meteo per una città, con supporto cache.

    Flusso:
    1. Controlla la cache → se presente e valida, restituisce i dati cached
    2. Altrimenti: geocoding → API meteo → salva in cache → restituisce

    Args:
        city: Nome della città.
        forecast_days: Giorni di previsione (1-16, default 5).
        use_cache: Se True, usa la cache (default True).

    Returns:
        Dizionario completo con info città e dati meteo::

            {
                "city": "Roma",
                "latitude": 41.89,
                "longitude": 12.51,
                "cached": False,
                "current": { ... },
                "forecast": [ ... ]
            }

    Raises:
        ValueError: Se il nome della città è vuoto.
        CityNotFoundError: Se la città non esiste.
        GeocodingAPIError: Per errori API geocoding.
        WeatherAPIError: Per errori API meteo.

    Example:
        >>> result = fetch_city_weather("Roma")
        >>> print(result["current"]["temperature_c"])
        22.5
    """
    # 1. Controlla cache
    if use_cache:
        cached = _cache.get(city)
        if cached is not None:
            cached["cached"] = True
            return cached

    # 2. Geocoding
    lat, lon, name = get_coordinates(city)

    # 3. Meteo
    weather = get_weather(lat, lon, forecast_days=forecast_days)

    result: dict[str, Any] = {
        "city": name,
        "latitude": lat,
        "longitude": lon,
        "cached": False,
        "current": weather["current"],
        "forecast": weather["forecast"],
    }

    # 4. Salva in cache
    if use_cache:
        _cache.set(city, result)

    return result


# ── Multi-città (parallelo) ──────────────────────────────────────────────────


def fetch_multiple_cities(
    cities: list[str], forecast_days: int = 5, use_cache: bool = True
) -> list[dict[str, Any]]:
    """Recupera i dati meteo per più città in parallelo.

    Usa un ThreadPoolExecutor per eseguire le chiamate API in parallelo,
    migliorando significativamente le prestazioni con molte città.
    Le città che causano errori vengono incluse nel risultato con un
    campo 'error' descrittivo.

    Args:
        cities: Lista di nomi di città.
        forecast_days: Giorni di previsione per ogni città (default 5).
        use_cache: Se True, usa la cache (default True).

    Returns:
        Lista di dizionari, uno per città. In caso di errore, il dizionario
        contiene le chiavi 'city' e 'error'.

    Example:
        >>> results = fetch_multiple_cities(["Roma", "Milano", "Napoli"])
        >>> for r in results:
        ...     if "error" in r:
        ...         print(f"{r['city']}: {r['error']}")
        ...     else:
        ...         print(f"{r['city']}: {r['current']['temperature_c']}°C")
    """
    results: list[dict[str, Any]] = []

    def _fetch_one(city_name: str) -> dict[str, Any]:
        try:
            return fetch_city_weather(city_name, forecast_days, use_cache)
        except (CityNotFoundError, GeocodingAPIError, WeatherAPIError, ValueError) as e:
            return {"city": city_name, "error": str(e)}

    workers = min(len(cities), MAX_PARALLEL_WORKERS)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_city = {
            executor.submit(_fetch_one, city): city for city in cities
        }
        for future in as_completed(future_to_city):
            results.append(future.result())

    # Riordina i risultati secondo l'ordine originale delle città
    city_order = {c.strip().lower(): i for i, c in enumerate(cities)}
    results.sort(key=lambda r: city_order.get(r.get("city", "").lower(), 999))

    return results


# ── Utility ───────────────────────────────────────────────────────────────────


def celsius_to_fahrenheit(celsius: float) -> float:
    """Converte una temperatura da Celsius a Fahrenheit.

    Args:
        celsius: Temperatura in gradi Celsius.

    Returns:
        Temperatura in gradi Fahrenheit, arrotondata a 1 decimale.

    Raises:
        TypeError: Se il valore non è numerico.

    Example:
        >>> celsius_to_fahrenheit(0)
        32.0
        >>> celsius_to_fahrenheit(100)
        212.0
    """
    if not isinstance(celsius, (int, float)):
        raise TypeError(f"Atteso valore numerico, ricevuto {type(celsius).__name__}")
    return round(celsius * 9 / 5 + 32, 1)


# Nomi dei giorni e mesi in italiano per la formattazione delle date
_GIORNI = [
    "Lunedì", "Martedì", "Mercoledì", "Giovedì",
    "Venerdì", "Sabato", "Domenica",
]
_MESI = [
    "", "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
    "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre",
]


def _format_date(date_str: str) -> str:
    """Formatta una data ISO (YYYY-MM-DD) in formato leggibile italiano.

    Args:
        date_str: Data in formato ISO 8601 (es. '2026-03-28').

    Returns:
        Data formattata (es. 'Sabato 28 Marzo 2026').
    """
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        giorno = _GIORNI[dt.weekday()]
        mese = _MESI[dt.month]
        return f"{giorno} {dt.day} {mese} {dt.year}"
    except (ValueError, IndexError):
        return date_str  # Fallback: restituisce la data originale
