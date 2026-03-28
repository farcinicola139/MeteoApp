"""Modulo per la formattazione dell'output meteo nel terminale.

Genera output leggibile e strutturato con colori ANSI opzionali
per la visualizzazione dei dati meteo nel terminale.
"""

from __future__ import annotations

from typing import Any

# ── Colori ANSI per il terminale ──────────────────────────────────────────────
BOLD = "\033[1m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
GREEN = "\033[92m"
RED = "\033[91m"
BLUE = "\033[94m"
RESET = "\033[0m"
DIM = "\033[2m"


def format_city_weather(data: dict[str, Any], show_forecast: bool = True) -> str:
    """Formatta i dati meteo di una città in un output leggibile per il terminale.

    Produce un output strutturato con:
    - Nome città e coordinate
    - Meteo corrente (temperatura, umidità, vento, precipitazioni)
    - Previsioni giornaliere (opzionale)

    Args:
        data: Dizionario restituito da ``fetch_city_weather()``.
            Deve contenere le chiavi 'city', 'current' e opzionalmente 'forecast'.
        show_forecast: Se True, mostra anche le previsioni giornaliere.

    Returns:
        Stringa formattata pronta per la stampa nel terminale.

    Example:
        >>> from meteo.weather import fetch_city_weather
        >>> data = fetch_city_weather("Roma")
        >>> print(format_city_weather(data))
    """
    if "error" in data:
        return f"\n{RED}✗ {data['city']}: {data['error']}{RESET}"

    lines: list[str] = []
    city = data.get("city", "Sconosciuta")
    lat = data.get("latitude", "?")
    lon = data.get("longitude", "?")
    cached = data.get("cached", False)

    # ── Header città ──
    cache_tag = f" {DIM}(dalla cache){RESET}" if cached else ""
    lines.append(f"\n{'═' * 60}")
    lines.append(f"{BOLD}{CYAN}☁  {city}{RESET}{cache_tag}")
    lines.append(f"{DIM}   Coordinate: {lat}, {lon}{RESET}")
    lines.append(f"{'─' * 60}")

    # ── Meteo corrente ──
    cur = data.get("current", {})
    lines.append(f"{BOLD}  📍 Meteo attuale:{RESET}")
    lines.append(
        f"     🌡  Temperatura: {YELLOW}{cur.get('temperature_c', '?')} °C{RESET}"
        f" / {cur.get('temperature_f', '?')} °F"
    )
    lines.append(
        f"     💧 Umidità:     {BLUE}{cur.get('humidity', '?')}%{RESET}"
    )
    lines.append(
        f"     💨 Vento:       {GREEN}{cur.get('wind_speed_kmh', '?')} km/h{RESET}"
    )
    lines.append(
        f"     🌧  Precipitaz.: {CYAN}{cur.get('precipitation_mm', '?')} mm{RESET}"
    )

    # ── Previsioni giornaliere ──
    if show_forecast and "forecast" in data:
        lines.append(f"\n{BOLD}  📅 Previsioni:{RESET}")
        for day in data["forecast"]:
            lines.append(f"{'─' * 60}")
            lines.append(f"  {BOLD}{day.get('date_readable', day.get('date', '?'))}{RESET}")
            lines.append(
                f"     🌡  Min: {BLUE}{day.get('temp_min_c', '?')} °C{RESET}"
                f" / {day.get('temp_min_f', '?')} °F"
                f"   │   Max: {RED}{day.get('temp_max_c', '?')} °C{RESET}"
                f" / {day.get('temp_max_f', '?')} °F"
            )
            lines.append(
                f"     💧 Umidità media: {day.get('humidity_mean', '?')}%"
                f"   │   💨 Vento max: {day.get('wind_speed_max_kmh', '?')} km/h"
            )
            lines.append(
                f"     🌧  Precipitazioni: {day.get('precipitation_sum_mm', '?')} mm"
            )

    lines.append(f"{'═' * 60}")
    return "\n".join(lines)


def format_multiple_cities(
    results: list[dict[str, Any]], show_forecast: bool = True
) -> str:
    """Formatta i dati meteo di più città in un output confrontabile.

    Args:
        results: Lista di dizionari restituiti da ``fetch_multiple_cities()``.
        show_forecast: Se True, mostra le previsioni per ogni città.

    Returns:
        Stringa formattata con i dati di tutte le città.
    """
    if not results:
        return f"\n{YELLOW}Nessun risultato disponibile.{RESET}"

    parts = [format_city_weather(r, show_forecast=show_forecast) for r in results]
    return "\n".join(parts)


def format_comparison_table(results: list[dict[str, Any]]) -> str:
    """Genera una tabella comparativa sintetica delle temperature correnti.

    Utile per confrontare rapidamente il meteo di più città.

    Args:
        results: Lista di dizionari restituiti da ``fetch_multiple_cities()``.

    Returns:
        Tabella formattata come stringa.

    Example:
        >>> print(format_comparison_table(results))
        ┌──────────────┬────────┬────────┬──────┬───────┬────────┐
        │ Città        │  °C    │  °F    │ Umid.│ Vento │ Pioggia│
        ├──────────────┼────────┼────────┼──────┼───────┼────────┤
        │ Roma         │  22.5  │  72.5  │  65% │ 12 kh │ 0.0 mm│
        │ Milano       │  18.3  │  64.9  │  72% │  8 kh │ 1.2 mm│
        └──────────────┴────────┴────────┴──────┴───────┴────────┘
    """
    lines: list[str] = []
    header = (
        f"\n{BOLD}{'Città':<16} {'°C':>6} {'°F':>6} "
        f"{'Umid.':>6} {'Vento':>8} {'Pioggia':>8}{RESET}"
    )
    lines.append(header)
    lines.append("─" * 56)

    for r in results:
        if "error" in r:
            lines.append(f"{r['city']:<16} {RED}{'Errore: ' + r['error'][:30]}{RESET}")
            continue

        cur = r.get("current", {})
        lines.append(
            f"{r.get('city', '?'):<16}"
            f" {cur.get('temperature_c', '?'):>6}"
            f" {cur.get('temperature_f', '?'):>6}"
            f" {str(cur.get('humidity', '?')) + '%':>6}"
            f" {str(cur.get('wind_speed_kmh', '?')) + ' km/h':>8}"
            f" {str(cur.get('precipitation_mm', '?')) + ' mm':>8}"
        )

    lines.append("─" * 56)
    return "\n".join(lines)
