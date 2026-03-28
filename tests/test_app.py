"""Test suite completa per l'applicazione meteo.

Copre:
- Conversione temperatura
- Geocoding (città valida, inesistente, errori API)
- Meteo corrente e previsioni
- Cache (set/get, scadenza, persistenza)
- Formattazione output
- Edge case (input vuoti, JSON malformato, chiavi mancanti)
"""

import json
import os
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

import requests

from meteo.cache import WeatherCache
from meteo.exceptions import CityNotFoundError, GeocodingAPIError, WeatherAPIError
from meteo.formatter import format_city_weather, format_comparison_table
from meteo.weather import (
    celsius_to_fahrenheit,
    fetch_city_weather,
    fetch_multiple_cities,
    get_coordinates,
    get_weather,
)


# ══════════════════════════════════════════════════════════════════════════════
# Test conversione temperatura
# ══════════════════════════════════════════════════════════════════════════════


class TestCelsiusToFahrenheit(unittest.TestCase):
    """Test per la conversione Celsius → Fahrenheit."""

    def test_zero(self):
        self.assertEqual(celsius_to_fahrenheit(0), 32.0)

    def test_positive(self):
        self.assertEqual(celsius_to_fahrenheit(100), 212.0)

    def test_negative(self):
        self.assertEqual(celsius_to_fahrenheit(-40), -40.0)

    def test_decimal(self):
        self.assertEqual(celsius_to_fahrenheit(11.6), 52.9)

    def test_type_error_string(self):
        with self.assertRaises(TypeError):
            celsius_to_fahrenheit("caldo")

    def test_type_error_none(self):
        with self.assertRaises(TypeError):
            celsius_to_fahrenheit(None)


# ══════════════════════════════════════════════════════════════════════════════
# Test geocoding
# ══════════════════════════════════════════════════════════════════════════════


class TestGetCoordinates(unittest.TestCase):
    """Test per la funzione get_coordinates."""

    @patch("meteo.weather.requests.get")
    def test_valid_city(self, mock_get):
        """Città valida restituisce coordinate corrette."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {"latitude": 35.6895, "longitude": 139.6917, "name": "Tokyo"}
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        lat, lon, name = get_coordinates("Tokyo")

        self.assertEqual(lat, 35.6895)
        self.assertEqual(lon, 139.6917)
        self.assertEqual(name, "Tokyo")

    @patch("meteo.weather.requests.get")
    def test_city_not_found_empty_response(self, mock_get):
        """Risposta senza 'results' solleva CityNotFoundError."""
        mock_response = MagicMock()
        mock_response.json.return_value = {}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        with self.assertRaises(CityNotFoundError) as ctx:
            get_coordinates("Xyzzyville")
        self.assertIn("Città non trovata", str(ctx.exception))

    @patch("meteo.weather.requests.get")
    def test_city_not_found_empty_results(self, mock_get):
        """'results' vuoto solleva CityNotFoundError."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"results": []}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        with self.assertRaises(CityNotFoundError):
            get_coordinates("Xyzzyville")

    def test_empty_string_raises_value_error(self):
        """Stringa vuota solleva ValueError."""
        with self.assertRaises(ValueError):
            get_coordinates("")

    def test_whitespace_only_raises_value_error(self):
        """Solo spazi solleva ValueError."""
        with self.assertRaises(ValueError):
            get_coordinates("   ")

    def test_non_string_raises_value_error(self):
        """Input non-stringa solleva ValueError."""
        with self.assertRaises(ValueError):
            get_coordinates(123)

    @patch("meteo.weather.requests.get")
    def test_only_one_api_call_on_not_found(self, mock_get):
        """Con città inesistente viene fatta solo 1 chiamata (geocoding)."""
        mock_response = MagicMock()
        mock_response.json.return_value = {}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        with self.assertRaises(CityNotFoundError):
            get_coordinates("Xyzzyville")

        mock_get.assert_called_once()


# ══════════════════════════════════════════════════════════════════════════════
# Test errori API geocoding
# ══════════════════════════════════════════════════════════════════════════════


class TestGeocodingAPIErrors(unittest.TestCase):
    """Test gestione errori API geocoding."""

    @patch("meteo.weather.requests.get")
    def test_timeout(self, mock_get):
        mock_get.side_effect = requests.Timeout()
        with self.assertRaises(GeocodingAPIError) as ctx:
            get_coordinates("Tokyo")
        self.assertIn("timeout", str(ctx.exception).lower())

    @patch("meteo.weather.requests.get")
    def test_connection_error(self, mock_get):
        mock_get.side_effect = requests.ConnectionError()
        with self.assertRaises(GeocodingAPIError) as ctx:
            get_coordinates("Tokyo")
        self.assertIn("connessione", str(ctx.exception).lower())

    @patch("meteo.weather.requests.get")
    def test_http_error(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.HTTPError(
            response=mock_response
        )
        mock_get.return_value = mock_response
        with self.assertRaises(GeocodingAPIError) as ctx:
            get_coordinates("Tokyo")
        self.assertIn("500", str(ctx.exception))

    @patch("meteo.weather.requests.get")
    def test_json_decode_error(self, mock_get):
        """Risposta non-JSON solleva GeocodingAPIError."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.side_effect = json.JSONDecodeError("err", "", 0)
        mock_get.return_value = mock_response

        with self.assertRaises(GeocodingAPIError) as ctx:
            get_coordinates("Tokyo")
        self.assertIn("non valida", str(ctx.exception))


# ══════════════════════════════════════════════════════════════════════════════
# Test meteo corrente e previsioni
# ══════════════════════════════════════════════════════════════════════════════


class TestGetWeather(unittest.TestCase):
    """Test per la funzione get_weather (corrente + forecast)."""

    @patch("meteo.weather.requests.get")
    def test_valid_weather_with_forecast(self, mock_get):
        """Coordinate valide restituiscono dati correnti e previsioni."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "current": {
                "temperature_2m": 22.5,
                "relative_humidity_2m": 65,
                "wind_speed_10m": 12.3,
                "precipitation": 0.0,
            },
            "daily": {
                "time": ["2026-03-28", "2026-03-29"],
                "temperature_2m_max": [24.1, 23.0],
                "temperature_2m_min": [14.2, 13.5],
                "relative_humidity_2m_max": [70, 68],
                "relative_humidity_2m_min": [50, 48],
                "wind_speed_10m_max": [18.5, 15.0],
                "precipitation_sum": [0.0, 2.1],
            },
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = get_weather(41.89, 12.51, forecast_days=2)

        # Dati correnti
        self.assertEqual(result["current"]["temperature_c"], 22.5)
        self.assertEqual(result["current"]["humidity"], 65)
        self.assertEqual(result["current"]["wind_speed_kmh"], 12.3)
        self.assertEqual(result["current"]["precipitation_mm"], 0.0)
        self.assertAlmostEqual(result["current"]["temperature_f"], 72.5, places=1)

        # Previsioni
        self.assertEqual(len(result["forecast"]), 2)
        self.assertEqual(result["forecast"][0]["temp_max_c"], 24.1)
        self.assertEqual(result["forecast"][1]["precipitation_sum_mm"], 2.1)

    @patch("meteo.weather.requests.get")
    def test_missing_current_data(self, mock_get):
        """Dati correnti mancanti sollevano WeatherAPIError."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"daily": {}}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        with self.assertRaises(WeatherAPIError) as ctx:
            get_weather(41.89, 12.51)
        self.assertIn("non disponibili", str(ctx.exception))


# ══════════════════════════════════════════════════════════════════════════════
# Test errori API meteo
# ══════════════════════════════════════════════════════════════════════════════


class TestWeatherAPIErrors(unittest.TestCase):
    """Test gestione errori API meteo."""

    @patch("meteo.weather.requests.get")
    def test_timeout(self, mock_get):
        mock_get.side_effect = requests.Timeout()
        with self.assertRaises(WeatherAPIError) as ctx:
            get_weather(35.68, 139.69)
        self.assertIn("timeout", str(ctx.exception).lower())

    @patch("meteo.weather.requests.get")
    def test_connection_error(self, mock_get):
        mock_get.side_effect = requests.ConnectionError()
        with self.assertRaises(WeatherAPIError) as ctx:
            get_weather(35.68, 139.69)
        self.assertIn("connessione", str(ctx.exception).lower())

    @patch("meteo.weather.requests.get")
    def test_http_error(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.raise_for_status.side_effect = requests.HTTPError(
            response=mock_response
        )
        mock_get.return_value = mock_response
        with self.assertRaises(WeatherAPIError) as ctx:
            get_weather(35.68, 139.69)
        self.assertIn("503", str(ctx.exception))

    @patch("meteo.weather.requests.get")
    def test_json_decode_error(self, mock_get):
        """Risposta non-JSON solleva WeatherAPIError."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.side_effect = json.JSONDecodeError("err", "", 0)
        mock_get.return_value = mock_response

        with self.assertRaises(WeatherAPIError) as ctx:
            get_weather(35.68, 139.69)
        self.assertIn("non valida", str(ctx.exception))


# ══════════════════════════════════════════════════════════════════════════════
# Test cache
# ══════════════════════════════════════════════════════════════════════════════


class TestWeatherCache(unittest.TestCase):
    """Test per il sistema di cache."""

    def setUp(self):
        """Crea una cache temporanea per ogni test."""
        self._tmpfile = tempfile.NamedTemporaryFile(
            suffix=".json", delete=False, mode="w"
        )
        self._tmpfile.close()
        self.cache = WeatherCache(cache_file=self._tmpfile.name, ttl_seconds=2)

    def tearDown(self):
        """Rimuove il file temporaneo."""
        try:
            os.unlink(self._tmpfile.name)
        except OSError:
            pass

    def test_set_and_get(self):
        """Set + get restituisce i dati corretti."""
        data = {"temperature_c": 22.5}
        self.cache.set("Roma", data)
        result = self.cache.get("Roma")
        self.assertEqual(result, data)

    def test_get_nonexistent(self):
        """Get su chiave inesistente restituisce None."""
        self.assertIsNone(self.cache.get("Atlantide"))

    def test_case_insensitive(self):
        """La cache è case-insensitive."""
        self.cache.set("Roma", {"temp": 20})
        self.assertIsNotNone(self.cache.get("roma"))
        self.assertIsNotNone(self.cache.get("ROMA"))

    def test_expiration(self):
        """I dati scadono dopo il TTL."""
        self.cache.set("Roma", {"temp": 20})
        time.sleep(2.5)
        self.assertIsNone(self.cache.get("Roma"))

    def test_clear(self):
        """Clear svuota tutta la cache."""
        self.cache.set("Roma", {"temp": 20})
        self.cache.set("Milano", {"temp": 18})
        self.cache.clear()
        self.assertIsNone(self.cache.get("Roma"))
        self.assertIsNone(self.cache.get("Milano"))

    def test_persistence(self):
        """I dati persistono su disco tra istanze."""
        self.cache.set("Roma", {"temp": 20})
        # Nuova istanza sullo stesso file
        cache2 = WeatherCache(cache_file=self._tmpfile.name, ttl_seconds=60)
        result = cache2.get("Roma")
        self.assertIsNotNone(result)
        self.assertEqual(result["temp"], 20)

    def test_cleanup_expired(self):
        """cleanup_expired rimuove le entry scadute."""
        self.cache.set("Roma", {"temp": 20})
        time.sleep(2.5)
        removed = self.cache.cleanup_expired()
        self.assertEqual(removed, 1)


# ══════════════════════════════════════════════════════════════════════════════
# Test formattazione
# ══════════════════════════════════════════════════════════════════════════════


class TestFormatter(unittest.TestCase):
    """Test per la formattazione dell'output."""

    def _make_data(self, city="Roma", temp=22.5):
        return {
            "city": city,
            "latitude": 41.89,
            "longitude": 12.51,
            "cached": False,
            "current": {
                "temperature_c": temp,
                "temperature_f": celsius_to_fahrenheit(temp),
                "humidity": 65,
                "wind_speed_kmh": 12.3,
                "precipitation_mm": 0.0,
            },
            "forecast": [
                {
                    "date": "2026-03-28",
                    "date_readable": "Sabato 28 Marzo 2026",
                    "temp_min_c": 14.2,
                    "temp_max_c": 24.1,
                    "temp_min_f": 57.6,
                    "temp_max_f": 75.4,
                    "humidity_mean": 60,
                    "wind_speed_max_kmh": 18.5,
                    "precipitation_sum_mm": 0.0,
                }
            ],
        }

    def test_format_contains_city_name(self):
        msg = format_city_weather(self._make_data())
        self.assertIn("Roma", msg)

    def test_format_contains_temperature(self):
        msg = format_city_weather(self._make_data())
        self.assertIn("22.5", msg)

    def test_format_contains_forecast(self):
        msg = format_city_weather(self._make_data(), show_forecast=True)
        self.assertIn("Sabato 28 Marzo 2026", msg)

    def test_format_error_city(self):
        data = {"city": "Xyzzy", "error": "Città non trovata"}
        msg = format_city_weather(data)
        self.assertIn("Xyzzy", msg)
        self.assertIn("non trovata", msg)

    def test_comparison_table(self):
        results = [
            self._make_data("Roma", 22.5),
            self._make_data("Milano", 18.3),
        ]
        table = format_comparison_table(results)
        self.assertIn("Roma", table)
        self.assertIn("Milano", table)


# ══════════════════════════════════════════════════════════════════════════════
# Test fetch multi-città
# ══════════════════════════════════════════════════════════════════════════════


class TestFetchMultipleCities(unittest.TestCase):
    """Test per il fetch parallelo di più città."""

    @patch("meteo.weather.get_weather")
    @patch("meteo.weather.get_coordinates")
    @patch("meteo.weather._cache")
    def test_returns_results_for_all_cities(self, mock_cache, mock_coords, mock_weather):
        """Restituisce un risultato per ogni città."""
        mock_cache.get.return_value = None
        mock_cache.set = MagicMock()
        mock_coords.side_effect = [
            (41.89, 12.51, "Roma"),
            (45.46, 9.18, "Milano"),
        ]
        mock_weather.return_value = {
            "current": {
                "temperature_c": 20, "temperature_f": 68,
                "humidity": 50, "wind_speed_kmh": 10, "precipitation_mm": 0,
            },
            "forecast": [],
        }

        results = fetch_multiple_cities(["Roma", "Milano"], use_cache=True)
        self.assertEqual(len(results), 2)

    @patch("meteo.weather.get_coordinates")
    @patch("meteo.weather._cache")
    def test_error_city_included_in_results(self, mock_cache, mock_coords):
        """Città con errore viene inclusa con campo 'error'."""
        mock_cache.get.return_value = None
        mock_coords.side_effect = CityNotFoundError("Xyzzy")

        results = fetch_multiple_cities(["Xyzzy"], use_cache=True)
        self.assertEqual(len(results), 1)
        self.assertIn("error", results[0])


if __name__ == "__main__":
    unittest.main()
