"""Entry point CLI dell'applicazione meteo.

Supporta:
- Singola città o lista di città (separate da virgola)
- Previsioni multi-giorno
- Tabella comparativa multi-città
- Cache automatica (1 ora)

Utilizzo:
    python main.py
"""

import sys

from meteo.exceptions import CityNotFoundError, GeocodingAPIError, WeatherAPIError
from meteo.formatter import format_comparison_table, format_multiple_cities
from meteo.weather import fetch_multiple_cities


def main() -> None:
    """Funzione principale CLI: chiede le città e mostra il meteo."""
    print("\n🌤️  Meteo App — Previsioni meteo multi-città\n")

    raw_input = input(
        "Inserisci una o più città (separate da virgola): "
    ).strip()

    if not raw_input:
        print("❌ Errore: inserisci almeno un nome di città.")
        sys.exit(1)

    # Parsing: split per virgola, rimuovi stringhe vuote e spazi
    cities = [c.strip() for c in raw_input.split(",") if c.strip()]

    if not cities:
        print("❌ Errore: nessuna città valida inserita.")
        sys.exit(1)

    print(f"\n🔍 Recupero dati meteo per: {', '.join(cities)}...")

    # Fetch parallelo con cache
    results = fetch_multiple_cities(cities, forecast_days=5, use_cache=True)

    # Mostra tabella comparativa se più di una città
    if len(cities) > 1:
        print(format_comparison_table(results))

    # Mostra dettagli completi per ogni città
    print(format_multiple_cities(results, show_forecast=True))


if __name__ == "__main__":
    main()
