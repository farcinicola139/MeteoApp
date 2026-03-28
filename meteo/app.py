"""Modulo di compatibilità — reindirizza ai nuovi moduli.

DEPRECATO: usare direttamente meteo.weather e meteo.exceptions.
Mantenuto per retrocompatibilità con codice esistente.
"""

# Re-export da nuovi moduli per retrocompatibilità
from meteo.exceptions import CityNotFoundError, GeocodingAPIError, WeatherAPIError
from meteo.weather import celsius_to_fahrenheit, get_coordinates, get_weather


def format_weather_message(city_name: str, lat: float, lon: float, temp_c: float) -> str:
    """Formatta il messaggio meteo (versione legacy).

    DEPRECATO: usare meteo.formatter.format_city_weather().
    """
    temp_f = celsius_to_fahrenheit(temp_c)
    return (
        f"\nMeteo attuale per {city_name} (lat: {lat}, lon: {lon}):\n"
        f"  Temperatura: {temp_c} °C / {temp_f} °F"
    )
