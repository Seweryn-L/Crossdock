"""Resolve paths to company Excel fixtures (Polish ł in filename)."""

from __future__ import annotations

from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent


def company_orders_fixture() -> Path:
    """Real e2open sample: przykładowe_dane_od_firmy.xlsx (header row 3)."""
    matches = sorted(FIXTURES_DIR.glob("*dane_od_firmy.xlsx"))
    if not matches:
        raise FileNotFoundError(f"Brak fixture firmy w {FIXTURES_DIR} (*dane_od_firmy.xlsx)")
    return matches[0]


def tms_orders_fixture() -> Path:
    """Truncated TMS export sample (optional secondary format)."""
    matches = sorted(FIXTURES_DIR.glob("*z_systemu_TMS.xlsx"))
    if not matches:
        raise FileNotFoundError(f"Brak fixture TMS w {FIXTURES_DIR} (*z_systemu_TMS.xlsx)")
    return matches[0]


def june_carrier_load_fixture() -> Path:
    """June 2026 e2open carrier load status sample (primary demo dataset)."""
    path = FIXTURES_DIR / "carrier_load_status1620780.xlsx"
    if not path.is_file():
        raise FileNotFoundError(f"Brak fixture czerwcowego: {path}")
    return path
