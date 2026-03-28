"""Modulo per calcoli astronomici: visibilità pianeti, fase lunare, eventi.

Utilizza la libreria PyEphem per calcoli astronomici locali.
Non richiede API key — tutti i calcoli sono effettuati offline.

Funzionalità:
- Pianeti visibili sopra l'orizzonte per una data posizione e orario
- Orari di levata e tramonto dei pianeti
- Fase lunare (percentuale e nome)
- Prossimi eventi astronomici notevoli
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any

import ephem


# ── Mappatura pianeti ─────────────────────────────────────────────────────────
_PLANET_CLASSES = {
    "Mercurio": ephem.Mercury,
    "Venere": ephem.Venus,
    "Marte": ephem.Mars,
    "Giove": ephem.Jupiter,
    "Saturno": ephem.Saturn,
    "Urano": ephem.Uranus,
    "Nettuno": ephem.Neptune,
}

_PLANET_EMOJI = {
    "Mercurio": "☿️",
    "Venere": "♀️",
    "Marte": "♂️",
    "Giove": "♃",
    "Saturno": "♄",
    "Urano": "⛢",
    "Nettuno": "♆",
}

# ── Nomi fasi lunari ─────────────────────────────────────────────────────────
_MOON_PHASE_NAMES = [
    ("Luna nuova", "🌑"),
    ("Luna crescente", "🌒"),
    ("Primo quarto", "🌓"),
    ("Gibbosa crescente", "🌔"),
    ("Luna piena", "🌕"),
    ("Gibbosa calante", "🌖"),
    ("Ultimo quarto", "🌗"),
    ("Luna calante", "🌘"),
]


def _create_observer(lat: float, lon: float, date: datetime | None = None) -> ephem.Observer:
    """Crea un oggetto Observer per la posizione e data specificate.

    Args:
        lat: Latitudine in gradi decimali.
        lon: Longitudine in gradi decimali.
        date: Data/ora UTC. Se None, usa l'ora corrente.

    Returns:
        Oggetto ephem.Observer configurato.
    """
    observer = ephem.Observer()
    observer.lat = str(lat)
    observer.lon = str(lon)
    observer.elevation = 0
    # Imposta orizzonte a -6° per crepuscolo civile (pianeti visibili)
    observer.horizon = "-6"
    if date:
        observer.date = ephem.Date(date)
    else:
        observer.date = ephem.now()
    return observer


def _ephem_date_to_str(d: ephem.Date) -> str:
    """Converte una data ephem in stringa HH:MM leggibile (ora locale approssimata).

    Args:
        d: Data ephem (UTC).

    Returns:
        Stringa orario formato "HH:MM UTC".
    """
    try:
        dt = ephem.Date(d).datetime()
        return dt.strftime("%H:%M UTC")
    except Exception:
        return "—"


def get_visible_planets(lat: float, lon: float) -> list[dict[str, Any]]:
    """Calcola quali pianeti sono attualmente visibili dalla posizione data.

    Un pianeta è considerato "visibile" se la sua altitudine è > 0°
    sopra l'orizzonte. Vengono anche forniti orari di levata e tramonto.

    Args:
        lat: Latitudine in gradi decimali.
        lon: Longitudine in gradi decimali.

    Returns:
        Lista di dizionari con info su ogni pianeta visibile::

            [
                {
                    "name": "Giove",
                    "emoji": "♃",
                    "altitude_deg": 45.2,
                    "azimuth_deg": 180.5,
                    "magnitude": -2.1,
                    "rise_time": "18:30 UTC",
                    "set_time": "04:15 UTC",
                    "constellation": "Taurus",
                    "visible": True
                },
                ...
            ]
    """
    observer = _create_observer(lat, lon)
    # Per il calcolo visibilità usiamo orizzonte standard (0°)
    observer.horizon = "0"
    planets = []

    for name, planet_class in _PLANET_CLASSES.items():
        try:
            body = planet_class()
            body.compute(observer)

            altitude_deg = math.degrees(float(body.alt))
            azimuth_deg = math.degrees(float(body.az))
            magnitude = float(body.mag)

            # Calcola orari levata e tramonto
            rise_time = "—"
            set_time = "—"
            try:
                rise = observer.next_rising(planet_class())
                rise_time = _ephem_date_to_str(rise)
            except (ephem.NeverUpError, ephem.AlwaysUpError, Exception):
                pass
            try:
                setting = observer.next_setting(planet_class())
                set_time = _ephem_date_to_str(setting)
            except (ephem.NeverUpError, ephem.AlwaysUpError, Exception):
                pass

            # Costellazione
            constellation = ""
            try:
                constellation = ephem.constellation(body)[1]
            except Exception:
                pass

            planets.append({
                "name": name,
                "emoji": _PLANET_EMOJI.get(name, ""),
                "altitude_deg": round(altitude_deg, 1),
                "azimuth_deg": round(azimuth_deg, 1),
                "magnitude": round(magnitude, 1),
                "rise_time": rise_time,
                "set_time": set_time,
                "constellation": constellation,
                "visible": altitude_deg > 0,
            })
        except Exception:
            continue

    return planets


def get_moon_phase() -> dict[str, Any]:
    """Calcola la fase lunare corrente.

    Returns:
        Dizionario con informazioni sulla fase lunare::

            {
                "phase_pct": 72.5,
                "phase_name": "Gibbosa crescente",
                "emoji": "🌔",
                "next_full_moon": "2026-04-05",
                "next_new_moon": "2026-04-19"
            }
    """
    moon = ephem.Moon()
    moon.compute(ephem.now())
    phase_pct = moon.phase  # 0-100

    # Determina se la luna è crescente o calante confrontando con ieri
    now = ephem.now()
    moon_yesterday = ephem.Moon()
    moon_yesterday.compute(ephem.Date(now - 1))
    is_waxing = moon.phase > moon_yesterday.phase

    # Determina nome fase basato sulla percentuale e direzione
    if phase_pct < 2:
        idx = 0  # Luna nuova
    elif phase_pct >= 98:
        idx = 4  # Luna piena
    elif phase_pct < 25:
        idx = 1 if is_waxing else 7  # Crescente / Calante
    elif phase_pct < 35:
        idx = 2 if is_waxing else 6  # Primo quarto / Ultimo quarto
    elif phase_pct < 75:
        idx = 3 if is_waxing else 5  # Gibbosa crescente / calante
    else:
        idx = 3 if is_waxing else 5  # Gibbosa crescente / calante

    phase_name, emoji = _MOON_PHASE_NAMES[idx]

    # Prossime fasi notevoli (riusa 'now' già calcolato sopra)
    next_full = ephem.next_full_moon(now).datetime().strftime("%Y-%m-%d")
    next_new = ephem.next_new_moon(now).datetime().strftime("%Y-%m-%d")
    next_first_quarter = ephem.next_first_quarter_moon(now).datetime().strftime("%Y-%m-%d")
    next_last_quarter = ephem.next_last_quarter_moon(now).datetime().strftime("%Y-%m-%d")

    return {
        "phase_pct": round(phase_pct, 1),
        "phase_name": phase_name,
        "emoji": emoji,
        "next_full_moon": next_full,
        "next_new_moon": next_new,
        "next_first_quarter": next_first_quarter,
        "next_last_quarter": next_last_quarter,
    }


def get_sun_info(lat: float, lon: float) -> dict[str, Any]:
    """Calcola orari alba e tramonto del sole per la posizione data.

    Args:
        lat: Latitudine in gradi decimali.
        lon: Longitudine in gradi decimali.

    Returns:
        Dizionario con orari alba/tramonto.
    """
    observer = _create_observer(lat, lon)
    observer.horizon = "0"
    sun = ephem.Sun()
    sun.compute(observer)

    result: dict[str, Any] = {}
    try:
        result["sunrise"] = _ephem_date_to_str(observer.next_rising(ephem.Sun()))
    except Exception:
        result["sunrise"] = "—"
    try:
        result["sunset"] = _ephem_date_to_str(observer.next_setting(ephem.Sun()))
    except Exception:
        result["sunset"] = "—"

    return result


def get_astronomical_events() -> list[dict[str, str]]:
    """Calcola i prossimi eventi astronomici notevoli (30 giorni).

    Restituisce eventi come:
    - Fasi lunari principali
    - Opposizioni / congiunzioni planetarie
    - Sciami meteorici noti (hardcoded per date approssimative)

    Returns:
        Lista di eventi con data e descrizione.
    """
    events: list[dict[str, str]] = []
    now = ephem.now()

    # ── Fasi lunari prossime ──
    phases = [
        ("Luna piena 🌕", ephem.next_full_moon(now)),
        ("Luna nuova 🌑", ephem.next_new_moon(now)),
        ("Primo quarto 🌓", ephem.next_first_quarter_moon(now)),
        ("Ultimo quarto 🌗", ephem.next_last_quarter_moon(now)),
    ]
    for name, date in phases:
        dt = ephem.Date(date).datetime()
        if dt - datetime.now(timezone.utc).replace(tzinfo=None) < timedelta(days=30):
            events.append({
                "date": dt.strftime("%Y-%m-%d"),
                "date_readable": dt.strftime("%d/%m/%Y"),
                "event": name,
                "type": "lunar",
            })

    # ── Sciami meteorici noti (date approssimative annuali) ──
    current_year = datetime.now(timezone.utc).year
    meteor_showers = [
        ("Quadrantidi ☄️", f"{current_year}-01-03", f"{current_year}-01-04"),
        ("Liridi ☄️", f"{current_year}-04-22", f"{current_year}-04-23"),
        ("Eta Aquaridi ☄️", f"{current_year}-05-06", f"{current_year}-05-07"),
        ("Delta Aquaridi ☄️", f"{current_year}-07-28", f"{current_year}-07-30"),
        ("Perseidi ☄️", f"{current_year}-08-12", f"{current_year}-08-13"),
        ("Draconidi ☄️", f"{current_year}-10-08", f"{current_year}-10-09"),
        ("Orionidi ☄️", f"{current_year}-10-21", f"{current_year}-10-22"),
        ("Leonidi ☄️", f"{current_year}-11-17", f"{current_year}-11-18"),
        ("Geminidi ☄️", f"{current_year}-12-13", f"{current_year}-12-14"),
        ("Ursidi ☄️", f"{current_year}-12-22", f"{current_year}-12-23"),
    ]
    now_dt = datetime.now(timezone.utc).replace(tzinfo=None)
    for name, start, end in meteor_showers:
        try:
            start_dt = datetime.strptime(start, "%Y-%m-%d")
            if timedelta(days=0) <= (start_dt - now_dt) <= timedelta(days=60):
                events.append({
                    "date": start,
                    "date_readable": start_dt.strftime("%d/%m/%Y"),
                    "event": name,
                    "type": "meteor_shower",
                })
        except ValueError:
            continue

    # ── Congiunzioni planetarie (controllo semplificato) ──
    # Verifica se due pianeti sono entro 5° l'uno dall'altro nei prossimi 30 giorni
    planet_pairs = [
        ("Venere", "Giove", ephem.Venus, ephem.Jupiter),
        ("Venere", "Marte", ephem.Venus, ephem.Mars),
        ("Giove", "Saturno", ephem.Jupiter, ephem.Saturn),
        ("Marte", "Giove", ephem.Mars, ephem.Jupiter),
        ("Marte", "Saturno", ephem.Mars, ephem.Saturn),
        ("Venere", "Saturno", ephem.Venus, ephem.Saturn),
    ]

    for name1, name2, cls1, cls2 in planet_pairs:
        for day_offset in range(0, 30, 1):
            check_date = ephem.Date(now + day_offset)
            try:
                p1 = cls1()
                p2 = cls2()
                p1.compute(check_date)
                p2.compute(check_date)
                sep = math.degrees(float(ephem.separation(p1, p2)))
                if sep < 3.0:
                    dt = ephem.Date(check_date).datetime()
                    event_str = f"Congiunzione {name1}-{name2} 🌟 ({sep:.1f}°)"
                    # Evita duplicati
                    if not any(e["event"].startswith(f"Congiunzione {name1}-{name2}") for e in events):
                        events.append({
                            "date": dt.strftime("%Y-%m-%d"),
                            "date_readable": dt.strftime("%d/%m/%Y"),
                            "event": event_str,
                            "type": "conjunction",
                        })
                    break
            except Exception:
                continue

    # Ordina per data
    events.sort(key=lambda e: e["date"])
    return events


def get_astronomy_data(lat: float, lon: float) -> dict[str, Any]:
    """Restituisce tutti i dati astronomici per una posizione.

    Funzione principale che aggrega tutte le informazioni astronomiche
    disponibili per la posizione specificata.

    Args:
        lat: Latitudine in gradi decimali.
        lon: Longitudine in gradi decimali.

    Returns:
        Dizionario completo con dati astronomici::

            {
                "planets": [...],
                "visible_count": 3,
                "moon": {...},
                "sun": {...},
                "events": [...]
            }
    """
    # Ogni componente è indipendente: se uno fallisce, gli altri continuano
    planets = []
    try:
        planets = get_visible_planets(lat, lon)
    except Exception:
        pass

    visible = [p for p in planets if p["visible"]]
    not_visible = [p for p in planets if not p["visible"]]

    moon = {"phase_pct": 0, "phase_name": "N/D", "emoji": "🌙",
            "next_full_moon": "—", "next_new_moon": "—"}
    try:
        moon = get_moon_phase()
    except Exception:
        pass

    sun = {"sunrise": "—", "sunset": "—"}
    try:
        sun = get_sun_info(lat, lon)
    except Exception:
        pass

    events: list[dict[str, str]] = []
    try:
        events = get_astronomical_events()
    except Exception:
        pass

    return {
        "planets_visible": visible,
        "planets_not_visible": not_visible,
        "visible_count": len(visible),
        "total_planets": len(planets),
        "moon": moon,
        "sun": sun,
        "events": events,
    }
