"""
Description:
    Ranks all weapons of a given class by three DPS metrics — raw burst, sustained
    (mag+reload cycle), and headshot-weighted sustained — to identify the strongest
    base weapon for each playstyle. Exotic placeholder rows (no numeric stats) are
    excluded. Accepts a weapon class as a command-line argument.

Source Data:
    data-lake/01_Bronze/division_2/*_ext_weapons_{class}.csv

Outputs:
    stdout: ranked table sorted by the chosen metric (default: headshot_dps)
    data-lake/02_Silver/division_2/{YYYYMMDD}_local_weapons_{class}_ranked.csv

Usage:
    python compare_weapons_local.py <weapon_class> [sort_by]
    weapon_class: assault_rifles | smgs | lmgs | rifles | mmrs | shotguns | pistols
    sort_by:      raw_dps | sustained_dps | headshot_dps  (default: headshot_dps)
"""

from __future__ import annotations
import csv
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from loader import load_weapons, Catalog
from models import Weapon, WEAPON_CLASSES

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SORT_OPTIONS = {"raw_dps", "sustained_dps", "headshot_dps"}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SILVER_DIR = os.path.normpath(
    os.path.join(SCRIPT_DIR, "..", "data-lake", "02_Silver", "division_2")
)

DISPLAY_COLS = [
    ("base_damage",     "Damage",  10),
    ("base_rpm",        "RPM",      6),
    ("base_mag_size",   "Mag",      5),
    ("base_reload_time","Reload",   7),
    ("optimal_range",   "Range",    6),
    ("hsd",             "HSD%",     6),
    ("raw_dps",         "Raw DPS", 12),
    ("sustained_dps",   "Sus DPS", 12),
    ("headshot_dps",    "HSD DPS", 12),
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _flag(w: Weapon) -> str:
    if w.is_exotic: return "[X]"
    if w.is_named:  return "[N]"
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
    if t.is_empty:   return "—"
    if t.is_fixed:   return t.value
    return f"[pool: {t.value}]"


def _build_talent_map(weapons: list, cat: Catalog) -> dict:
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

def rank_weapons(weapon_class: str, sort_by: str) -> tuple[list, list]:
    weapons = load_weapons(weapon_class)
    scoreable = [w for w in weapons if w.has_base_stats]
    excluded  = [w for w in weapons if not w.has_base_stats]
    ranked = sorted(scoreable, key=lambda w: _val(w, sort_by), reverse=True)
    return ranked, excluded


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def print_table(ranked: list, sort_by: str) -> None:
    name_w  = 36
    flag_w  = 4

    header = f"{'#':>3}  {'':>{flag_w}}{'Name':<{name_w}}"
    for attr, label, width in DISPLAY_COLS:
        header += f"  {label:>{width}}"
    print(header)
    print("-" * len(header))

    for rank, w in enumerate(ranked, 1):
        marker = ">>>" if rank == 1 else f"{rank:>3}"
        row = f"{marker}  {_flag(w):>{flag_w}}{w.name:<{name_w}}"
        for attr, label, width in DISPLAY_COLS:
            row += f"  {_fmt(attr, _val(w, attr)):>{width}}"
        print(row)

    print()
    sort_label = {
        "raw_dps":       "Raw Burst DPS",
        "sustained_dps": "Sustained DPS (mag+reload)",
        "headshot_dps":  "Headshot DPS (sustained × HSD)",
    }.get(sort_by, sort_by)
    print(f"Sorted by: {sort_label}  |  [N] = named  [X] = exotic")


# ---------------------------------------------------------------------------
# Save to Silver
# ---------------------------------------------------------------------------

def save_silver(weapon_class: str, ranked: list, sort_by: str) -> str:
    os.makedirs(SILVER_DIR, exist_ok=True)
    run_date = datetime.now().strftime("%Y%m%d")
    path = os.path.join(SILVER_DIR, f"{run_date}_local_weapons_{weapon_class}_ranked.csv")

    fieldnames = [
        "rank", "name", "flag", "family",
        "base_damage", "base_rpm", "base_mag_size", "base_reload_time",
        "optimal_range", "hsd",
        "raw_dps", "sustained_dps", "headshot_dps",
        "sort_by",
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
                "sort_by":          sort_by,
            })
    return path


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: python compare_weapons_local.py <weapon_class> [sort_by]")
        print(f"  weapon_class: {' | '.join(WEAPON_CLASSES)}")
        print(f"  sort_by:      {' | '.join(sorted(SORT_OPTIONS))}  (default: headshot_dps)")
        sys.exit(1)

    weapon_class = sys.argv[1]
    sort_by      = sys.argv[2] if len(sys.argv) > 2 else "headshot_dps"

    if weapon_class not in WEAPON_CLASSES:
        print(f"Unknown weapon class '{weapon_class}'. Valid: {sorted(WEAPON_CLASSES)}")
        sys.exit(1)
    if sort_by not in SORT_OPTIONS:
        print(f"Invalid sort_by '{sort_by}'. Choose from: {', '.join(sorted(SORT_OPTIONS))}")
        sys.exit(1)

    print(f"=== Weapon Comparison: {weapon_class.replace('_', ' ').title()} ===\n")

    ranked, excluded = rank_weapons(weapon_class, sort_by)

    if excluded:
        print(f"Note: {len(excluded)} exotic placeholder(s) excluded (no base stats):")
        for w in excluded:
            print(f"  {w.name}")
        print()

    print_table(ranked, sort_by)

    path = save_silver(weapon_class, ranked, sort_by)
    print(f"\nSaved: {path}")
