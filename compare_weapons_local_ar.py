"""
Description:
    Ranks all assault rifles by three DPS metrics — raw burst, sustained (mag+reload
    cycle), and headshot-weighted sustained — to identify the strongest base weapon
    for each playstyle. Exotic placeholder rows (no numeric stats) are excluded.
    Outputs a ranked table to stdout and saves a CSV to the Silver layer.

Source Data:
    data-lake/01_Bronze/division_2/*_ext_weapons_assault_rifles.csv

Outputs:
    stdout: ranked table sorted by the chosen metric (default: headshot_dps)
    data-lake/02_Silver/division_2/{YYYYMMDD}_local_weapons_ar_ranked.csv
"""

from __future__ import annotations
import csv
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from loader import load_weapons, Catalog
from models import Weapon

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

WEAPON_CLASS = "assault_rifles"
SORT_BY = "headshot_dps"   # raw_dps | sustained_dps | headshot_dps

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SILVER_DIR = os.path.normpath(
    os.path.join(SCRIPT_DIR, "..", "data-lake", "02_Silver", "division_2")
)

# Stat columns to include in the output (order matters for table display)
DISPLAY_COLS = [
    ("base_damage",    "Damage",    10),
    ("base_rpm",       "RPM",        6),
    ("base_mag_size",  "Mag",        5),
    ("base_reload_time","Reload",    7),
    ("optimal_range",  "Range",      6),
    ("hsd",            "HSD%",       6),
    ("raw_dps",        "Raw DPS",   12),
    ("sustained_dps",  "Sus DPS",   12),
    ("headshot_dps",   "HSD DPS",   12),
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _flag(w: Weapon) -> str:
    if w.is_exotic:
        return "[X]"
    if w.is_named:
        return "[N]"
    return "   "


def _val(w: Weapon, attr: str) -> float:
    return getattr(w, attr, 0.0)


def _fmt(attr: str, value: float) -> str:
    if attr in ("raw_dps", "sustained_dps", "headshot_dps"):
        return f"{value:,.0f}"
    if attr == "base_damage":
        return f"{value:,.0f}"
    if attr == "base_reload_time":
        return f"{value:.2f}s"
    if attr == "hsd":
        return f"{value:.0f}%"
    return str(int(value))


def _talent_label(w: Weapon) -> str:
    t = w.talent_slot
    if t.is_empty:
        return "—"
    if t.is_fixed:
        return t.value
    return f"[pool: {t.value}]"


# ---------------------------------------------------------------------------
# Resolve talents for display via Catalog
# ---------------------------------------------------------------------------

def _build_talent_map(weapons: list, cat: Catalog) -> dict:
    """Map weapon name → resolved talent name(s) for display."""
    result = {}
    for w in weapons:
        resolved = cat.resolve_weapon_talent(w.talent_slot)
        if not resolved:
            result[w.name] = _talent_label(w)
        elif w.talent_slot.is_fixed:
            result[w.name] = resolved[0].name
        else:
            result[w.name] = f"{len(resolved)} options"
    return result


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------

def rank_assault_rifles(sort_by: str = SORT_BY) -> list:
    weapons = load_weapons(WEAPON_CLASS)
    scoreable = [w for w in weapons if w.has_base_stats]
    excluded = [w for w in weapons if not w.has_base_stats]

    if excluded:
        print(f"Note: {len(excluded)} exotic placeholder(s) excluded (no base stats):")
        for w in excluded:
            print(f"  {w.name}")
        print()

    ranked = sorted(scoreable, key=lambda w: _val(w, sort_by), reverse=True)
    return ranked


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def print_table(ranked: list, talent_map: dict, sort_by: str = SORT_BY) -> None:
    name_w = 36
    flag_w = 4
    talent_w = 32

    # Header
    header = f"{'#':>3}  {'':>{flag_w}}{'Name':<{name_w}}"
    for attr, label, width in DISPLAY_COLS:
        header += f"  {label:>{width}}"
    header += f"  {'Talent':<{talent_w}}"
    print(header)
    print("-" * len(header))

    for rank, w in enumerate(ranked, 1):
        marker = ">>>" if rank == 1 else f"{rank:>3}"
        row = f"{marker}  {_flag(w):>{flag_w}}{w.name:<{name_w}}"
        for attr, label, width in DISPLAY_COLS:
            val = _val(w, attr)
            row += f"  {_fmt(attr, val):>{width}}"
        row += f"  {talent_map.get(w.name, '—'):<{talent_w}}"
        print(row)

    print()
    sort_label = {
        "raw_dps": "Raw Burst DPS",
        "sustained_dps": "Sustained DPS (mag+reload)",
        "headshot_dps": "Headshot DPS (sustained × HSD)",
    }.get(sort_by, sort_by)
    print(f"Sorted by: {sort_label}  |  [N] = named  [X] = exotic")


# ---------------------------------------------------------------------------
# Save to Silver
# ---------------------------------------------------------------------------

def save_silver(ranked: list, talent_map: dict, sort_by: str = SORT_BY) -> str:
    os.makedirs(SILVER_DIR, exist_ok=True)
    run_date = datetime.now().strftime("%Y%m%d")
    filename = f"{run_date}_local_weapons_ar_ranked.csv"
    path = os.path.join(SILVER_DIR, filename)

    fieldnames = [
        "rank", "name", "flag", "family",
        "base_damage", "base_rpm", "base_mag_size", "base_reload_time",
        "optimal_range", "hsd",
        "raw_dps", "sustained_dps", "headshot_dps",
        "talent", "sort_by",
    ]

    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for rank, w in enumerate(ranked, 1):
            writer.writerow({
                "rank":             rank,
                "name":             w.name,
                "flag":             _flag(w).strip() or "base",
                "family":           w.family,
                "base_damage":      w.base_damage,
                "base_rpm":         w.base_rpm,
                "base_mag_size":    w.base_mag_size,
                "base_reload_time": w.base_reload_time,
                "optimal_range":    w.optimal_range,
                "hsd":              w.hsd,
                "raw_dps":          round(w.raw_dps, 0),
                "sustained_dps":    round(w.sustained_dps, 0),
                "headshot_dps":     round(w.headshot_dps, 0),
                "talent":           talent_map.get(w.name, "—"),
                "sort_by":          sort_by,
            })
    return path


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sort_by = sys.argv[1] if len(sys.argv) > 1 else SORT_BY

    valid = {"raw_dps", "sustained_dps", "headshot_dps"}
    if sort_by not in valid:
        print(f"Invalid sort_by '{sort_by}'. Choose from: {', '.join(sorted(valid))}")
        sys.exit(1)

    print(f"=== Assault Rifle Comparison ===\n")

    cat = Catalog()
    ranked = rank_assault_rifles(sort_by)
    talent_map = _build_talent_map(ranked, cat)

    print_table(ranked, talent_map, sort_by)

    path = save_silver(ranked, talent_map, sort_by)
    print(f"Saved: {path}")
