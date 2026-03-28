"""Eccezioni personalizzate per l'applicazione meteo."""


class CityNotFoundError(Exception):
    """Eccezione sollevata quando la città non viene trovata nell'API di geocoding.

    Attributes:
        city: Nome della città cercata.
    """

    def __init__(self, city: str) -> None:
        self.city = city
        super().__init__(f"Città non trovata: '{city}'.")


class GeocodingAPIError(Exception):
    """Eccezione per errori nell'API di geocoding (connessione, timeout, HTTP)."""
    pass


class WeatherAPIError(Exception):
    """Eccezione per errori nell'API meteo (connessione, timeout, HTTP, dati mancanti)."""
    pass
