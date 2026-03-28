"""Pacchetto meteo — Applicazione meteo modulare con cache e API REST.

Moduli:
    exceptions: Eccezioni personalizzate
    cache:      Sistema di caching JSON con scadenza
    weather:    Chiamate API (geocoding, meteo, previsioni)
    formatter:  Formattazione output terminale
    api:        Backend REST (FastAPI)
"""

from meteo.exceptions import CityNotFoundError, GeocodingAPIError, WeatherAPIError
from meteo.weather import (
    celsius_to_fahrenheit,
    fetch_city_weather,
    fetch_multiple_cities,
    get_coordinates,
    get_weather,
)

__all__ = [
    "CityNotFoundError",
    "GeocodingAPIError",
    "WeatherAPIError",
    "get_coordinates",
    "get_weather",
    "celsius_to_fahrenheit",
    "fetch_city_weather",
    "fetch_multiple_cities",
]
