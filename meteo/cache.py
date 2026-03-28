"""Sistema di caching basato su file JSON con scadenza temporale.

Il cache salva i dati meteo per ogni città su file JSON locale.
Ogni entry ha un timestamp e scade dopo un intervallo configurabile (default: 1 ora).

Struttura del file cache (meteo_cache.json):
{
    "roma": {
        "timestamp": 1711640000.0,
        "data": { ... dati meteo ... }
    }
}
"""

from __future__ import annotations

import json
import os
import threading
import time
from typing import Any

# Durata default della cache: 1 ora (3600 secondi)
DEFAULT_TTL_SECONDS: int = 3600
DEFAULT_CACHE_FILE: str = "meteo_cache.json"


class WeatherCache:
    """Cache in-memory con persistenza su file JSON per i dati meteo.

    Combina un dizionario in memoria (per velocità) con un file JSON
    su disco (per persistenza tra esecuzioni).

    Args:
        cache_file: Percorso del file JSON di cache.
        ttl_seconds: Tempo di vita delle entry in secondi.

    Example:
        >>> cache = WeatherCache(ttl_seconds=3600)
        >>> cache.set("roma", {"temperature": 22.5})
        >>> cache.get("roma")
        {"temperature": 22.5}
        >>> # Dopo 1 ora:
        >>> cache.get("roma")
        None
    """

    def __init__(
        self,
        cache_file: str = DEFAULT_CACHE_FILE,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> None:
        self._cache_file = cache_file
        self._ttl = ttl_seconds
        self._memory: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._load_from_disk()

    def _load_from_disk(self) -> None:
        """Carica il cache dal file JSON su disco, se esiste."""
        if os.path.exists(self._cache_file):
            try:
                with open(self._cache_file, "r", encoding="utf-8") as f:
                    self._memory = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._memory = {}

    def _save_to_disk(self) -> None:
        """Salva il cache corrente su file JSON."""
        try:
            with open(self._cache_file, "w", encoding="utf-8") as f:
                json.dump(self._memory, f, ensure_ascii=False, indent=2)
        except OSError:
            pass  # Fallback silenzioso: la cache in memoria funziona comunque

    def _normalize_key(self, city: str) -> str:
        """Normalizza il nome della città come chiave di cache (lowercase, stripped)."""
        return city.strip().lower()

    def get(self, city: str) -> dict[str, Any] | None:
        """Recupera i dati dalla cache se presenti e non scaduti.

        Thread-safe: usa un lock per evitare race condition.

        Args:
            city: Nome della città.

        Returns:
            Dizionario con i dati meteo, oppure None se non in cache o scaduto.
        """
        key = self._normalize_key(city)
        with self._lock:
            entry = self._memory.get(key)

            if entry is None:
                return None

            # Controlla scadenza
            elapsed = time.time() - entry.get("timestamp", 0)
            if elapsed > self._ttl:
                # Entry scaduta, rimuovila
                del self._memory[key]
                self._save_to_disk()
                return None

            return entry.get("data")

    def set(self, city: str, data: dict[str, Any]) -> None:
        """Salva i dati meteo nella cache con timestamp corrente.

        Thread-safe: usa un lock per evitare race condition.

        Args:
            city: Nome della città.
            data: Dizionario con i dati meteo da salvare.
        """
        key = self._normalize_key(city)
        with self._lock:
            self._memory[key] = {
                "timestamp": time.time(),
                "data": data,
            }
            self._save_to_disk()

    def clear(self) -> None:
        """Svuota completamente la cache (memoria e disco)."""
        with self._lock:
            self._memory = {}
            self._save_to_disk()

    def cleanup_expired(self) -> int:
        """Rimuove tutte le entry scadute dalla cache.

        Returns:
            Numero di entry rimosse.
        """
        with self._lock:
            now = time.time()
            expired_keys = [
                k for k, v in self._memory.items()
                if now - v.get("timestamp", 0) > self._ttl
            ]
            for k in expired_keys:
                del self._memory[k]

            if expired_keys:
                self._save_to_disk()

            return len(expired_keys)
