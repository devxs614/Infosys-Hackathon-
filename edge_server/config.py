"""Environment-backed configuration with safe defaults for offline demos."""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True, slots=True)
class Settings:
    app_env: str = "development"
    host: str = "0.0.0.0"
    port: int = 8000
    gemini_api_key: str = ""
    gemini_model: str = "auto"
    tiger_db_url: str = ""
    osrm_url: str = "https://router.project-osrm.org"
    shift_minutes: int = 240
    demo_seconds: int = 180
    tick_ms: int = 500
    use_osrm: bool = True
    use_tiger: bool = True
    use_gemini: bool = True
    monterrey_lat: float = 25.6866
    monterrey_lon: float = -100.3161
    scenario_seed: int = 42


def get_settings() -> Settings:
    """Read configuration once per service factory; never log secret fields."""
    load_dotenv()
    return Settings(
        app_env=os.getenv("APP_ENV", "development"), host=os.getenv("HOST", "0.0.0.0"),
        port=_int("PORT", 8000), gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
        gemini_model=os.getenv("GEMINI_MODEL", "auto").strip() or "auto", tiger_db_url=os.getenv("TIGER_DB_URL", ""),
        osrm_url=os.getenv("OSRM_URL", "https://router.project-osrm.org").rstrip("/"),
        shift_minutes=_int("SHIFT_MINUTES", 240), demo_seconds=_int("DEMO_SECONDS", 180),
        tick_ms=_int("TICK_MS", 500), use_osrm=_bool("USE_OSRM", True),
        use_tiger=_bool("USE_TIGER", True), use_gemini=_bool("USE_GEMINI", True),
        monterrey_lat=_float("MONTERREY_LAT", 25.6866), monterrey_lon=_float("MONTERREY_LON", -100.3161),
        scenario_seed=_int("SCENARIO_SEED", 42),
    )
