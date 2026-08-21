"""
Description:
    Functions for loading Division 2 Bronze layer CSVs into model objects.
    Each load_* function finds the most recent dated file for its category,
    reads it with csv.DictReader, and returns a list of typed model instances.
    A Catalog class loads and indexes all reference tables in one shot for
    efficient cross-table lookups during analysis.

Source Data:
    data-lake/01_Bronze/division_2/{YYYYMMDD}_ext_*.csv

Outputs:
    Module — call load_weapons(), load_gear(), Catalog(), etc. from analysis scripts.
"""

from __future__ import annotations
import csv
import glob
import os
from models import (
    Weapon, GearPiece,
    WeaponMod, WeaponTalent,
    GearMod, GearTalent,
    BrandSet, GearSet, Attribute,
    WEAPON_CLASSES, GEAR_SLOTS,
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BRONZE_DIR = os.path.normpath(
    os.path.join(SCRIPT_DIR, "..", "data-lake", "01_Bronze", "division_2")
)
CORRECTIONS_PATH = os.path.join(SCRIPT_DIR, "brand_set_corrections.csv")

# Singular slot name → plural used in the Bronze filename
_GEAR_SLOT_FILE = {
    "mask":     "ext_gear_masks",
    "backpack": "ext_gear_backpacks",
    "chest":    "ext_gear_chests",
    "gloves":   "ext_gear_gloves",
    "holster":  "ext_gear_holsters",
    "knees":    "ext_gear_knees",
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _latest(file_key: str) -> str:
    """Return the path of the most recent Bronze file whose name contains file_key.

    Sorts descending so a higher date prefix wins, and a _vN suffix beats an
    un-versioned file on the same date (since '_' > '.' in ASCII).

    file_key examples:
        "ext_weapons_assault_rifles"
        "ext_gear_masks"
        "ext_attributes_all"
    """
    pattern = os.path.join(BRONZE_DIR, f"*_{file_key}*.csv")
    matches = glob.glob(pattern)
    if not matches:
        raise FileNotFoundError(
            f"No Bronze file found matching: *_{file_key}*.csv\n"
            f"  Searched in: {BRONZE_DIR}\n"
            f"  Run td2/fetch_div2hub.py to populate the Bronze layer."
        )
    return sorted(matches, reverse=True)[0]


def _read(file_key: str) -> list:
    path = _latest(file_key)
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _split_pipe(value: str) -> list:
    """Split a pipe-delimited compatibility string into a clean list."""
    if not value or value.strip() == "N/A":
        return []
    return [v.strip() for v in value.split("|") if v.strip()]


def _parse_stats(value: str) -> dict:
    """Parse a weapon mod stats string into a dict.

    "headshot-damage:30%|reload-speed:-10%"  →  {"headshot-damage": "30%", "reload-speed": "-10%"}
    """
    if not value or value.strip() == "N/A":
        return {}
    result = {}
    for part in value.split("|"):
        part = part.strip()
        if ":" in part:
            k, v = part.split(":", 1)
            result[k.strip()] = v.strip()
    return result


# ---------------------------------------------------------------------------
# Weapon loaders
# ---------------------------------------------------------------------------

def load_weapons(weapon_class: str) -> list:
    """Load all weapons from one weapon-class CSV.

    weapon_class must be one of: assault_rifles, smgs, lmgs, rifles, mmrs,
    shotguns, pistols.
    """
    if weapon_class not in WEAPON_CLASSES:
        raise ValueError(f"Unknown weapon class: {weapon_class!r}. Must be one of {WEAPON_CLASSES}")
    rows = _read(f"ext_weapons_{weapon_class}")
    return [Weapon.from_row(row, weapon_class) for row in rows]


def load_all_weapons() -> list:
    """Load every weapon across all seven weapon-class CSVs."""
    weapons = []
    for wc in WEAPON_CLASSES:
        weapons.extend(load_weapons(wc))
    return weapons


def load_weapon_mods() -> list:
    """Load all weapon attachment mods."""
    rows = _read("ext_weapons_mods")
    return [
        WeaponMod(
            name=row["name"],
            category=row["category"],
            compatibility=_split_pipe(row["compatibility"]),
            stats=_parse_stats(row["stats"]),
        )
        for row in rows
    ]


def load_weapon_talents() -> list:
    """Load all weapon talents."""
    rows = _read("ext_weapons_talents")
    return [
        WeaponTalent(
            name=row["name"],
            compatibility=_split_pipe(row["compatibility"]),
            description=row["description"],
        )
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Gear loaders
# ---------------------------------------------------------------------------

def load_gear(slot_type: str) -> list:
    """Load all items for one gear slot.

    slot_type must be one of: mask, backpack, chest, gloves, holster, knees.
    """
    if slot_type not in GEAR_SLOTS:
        raise ValueError(f"Unknown gear slot: {slot_type!r}. Must be one of {GEAR_SLOTS}")
    rows = _read(_GEAR_SLOT_FILE[slot_type])
    return [GearPiece.from_row(row, slot_type) for row in rows]


def load_all_gear() -> list:
    """Load every gear piece across all six slot CSVs."""
    pieces = []
    for slot in GEAR_SLOTS:
        pieces.extend(load_gear(slot))
    return pieces


def load_gear_mods() -> list:
    """Load all gear mod types."""
    rows = _read("ext_gear_gear_mods")
    return [
        GearMod(
            id=row["id"],
            stat_id=row["stat_id"],
            range_min=row["range_min"],
            range_max=row["range_max"],
            compatibility=_split_pipe(row["compatibility"]),
            category=row["category"],
            fidelity=row["fidelity"],
        )
        for row in rows
    ]


def load_gear_talents() -> list:
    """Load all gear talents (chest and backpack)."""
    rows = _read("ext_gear_gear_talents")
    return [
        GearTalent(
            name=row["name"],
            compatibility=_split_pipe(row["compatibility"]),
            description=row["description"],
        )
        for row in rows
    ]


def _load_brand_corrections() -> dict[str, dict]:
    """Return a name-keyed dict of correction rows from brand_set_corrections.csv.

    Returns an empty dict if the corrections file does not exist.
    Each correction row overrides the matching brand's fields entirely.
    """
    if not os.path.exists(CORRECTIONS_PATH):
        return {}
    with open(CORRECTIONS_PATH, encoding="utf-8", newline="") as f:
        return {row["name"]: row for row in csv.DictReader(f)}


def load_brand_sets(verbose: bool = False) -> list:
    """Load all brand sets with their 1/2/3-piece bonuses.

    Applies local corrections from brand_set_corrections.csv when present,
    overriding fields sourced from the upstream Bronze layer for verified brands.
    Set verbose=True to print a summary of applied corrections.
    """
    rows = _read("ext_gear_brand_sets")
    corrections = _load_brand_corrections()

    brands = []
    for row in rows:
        corr = corrections.get(row["name"])
        if corr:
            if verbose:
                print(f"  [correction] {row['name']}: {corr.get('note', '')}")
            brands.append(BrandSet(
                name=row["name"],
                default_core_stat_id=corr.get("default_core_stat_id") or row["default_core_stat_id"],
                bonus_1pc=corr.get("1pc_bonus") or row["1pc_bonus"],
                bonus_2pc=corr.get("2pc_bonus") or row["2pc_bonus"],
                bonus_3pc=corr.get("3pc_bonus") or row["3pc_bonus"],
            ))
        else:
            brands.append(BrandSet(
                name=row["name"],
                default_core_stat_id=row["default_core_stat_id"],
                bonus_1pc=row["1pc_bonus"],
                bonus_2pc=row["2pc_bonus"],
                bonus_3pc=row["3pc_bonus"],
            ))

    if corrections and not verbose:
        applied = [n for n in corrections if any(b.name == n for b in brands)]
        if applied:
            print(f"  [brand corrections applied: {', '.join(applied)}]")

    return brands


def load_gear_sets() -> list:
    """Load all gear sets with their 2/3/4-piece bonuses."""
    rows = _read("ext_gear_gear_sets")
    return [
        GearSet(
            name=row["name"],
            default_core_stat_id=row["default_core_stat_id"],
            bonus_1pc=row["1pc_bonus"],
            bonus_2pc=row["2pc_bonus"],
            bonus_3pc=row["3pc_bonus"],
            bonus_4pc=row["4pc_bonus"],
        )
        for row in rows
    ]


def load_attributes() -> list:
    """Load all attribute definitions (weapon cores/minors, gear cores/minors, named-item fixed stats)."""
    rows = _read("ext_attributes_all")
    return [
        Attribute(
            id=row["id"],
            stat_id=row["stat_id"],
            range_min=row["range_min"],
            range_max=row["range_max"],
            proto_max=row["proto_max"],
            compatibility=_split_pipe(row["compatibility"]),
            category=row["category"],
            fidelity=row["fidelity"],
        )
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Catalog — all reference data loaded and indexed in one object
# ---------------------------------------------------------------------------

class Catalog:
    """Loads every reference table once and exposes indexed lookups.

    Usage:
        cat = Catalog()
        eligible_mods = cat.mods_for_pool("optics-normal")
        talents = cat.talents_for_weapon_family("assault-rifle")
        brand = cat.brand_set("Badger Tuff")
    """

    def __init__(self):
        self.weapon_mods: list = load_weapon_mods()
        self.weapon_talents: list = load_weapon_talents()
        self.gear_mods: list = load_gear_mods()
        self.gear_talents: list = load_gear_talents()
        self.brand_sets: list = load_brand_sets()
        self.gear_sets: list = load_gear_sets()
        self.attributes: list = load_attributes()

        # name/id indexes for O(1) lookups
        self._weapon_mod_by_name: dict = {m.name: m for m in self.weapon_mods}
        self._weapon_talent_by_name: dict = {t.name: t for t in self.weapon_talents}
        self._gear_talent_by_name: dict = {t.name: t for t in self.gear_talents}
        self._brand_set_by_name: dict = {b.name: b for b in self.brand_sets}
        self._gear_set_by_name: dict = {g.name: g for g in self.gear_sets}
        self._attribute_by_id: dict = {a.id: a for a in self.attributes}
        self._attribute_by_stat_id: dict = {}
        for a in self.attributes:
            self._attribute_by_stat_id.setdefault(a.stat_id, []).append(a)

    # --- weapon mod lookups ------------------------------------------------

    def mods_for_pool(self, pool: str) -> list:
        """All weapon mods eligible for an attachment slot with pool key `pool`."""
        return [m for m in self.weapon_mods if m.fits(pool)]

    def mod_by_name(self, name: str):
        return self._weapon_mod_by_name.get(name)

    # --- weapon talent lookups ---------------------------------------------

    def talents_for_weapon_family(self, family: str) -> list:
        """All weapon talents that can roll on weapons of the given family."""
        return [t for t in self.weapon_talents if t.fits(family)]

    def weapon_talent_by_name(self, name: str):
        return self._weapon_talent_by_name.get(name)

    # --- gear talent lookups -----------------------------------------------

    def talents_for_slot(self, slot_type: str) -> list:
        """All gear talents compatible with a chest or backpack slot."""
        return [t for t in self.gear_talents if t.fits(slot_type)]

    def gear_talent_by_name(self, name: str):
        return self._gear_talent_by_name.get(name)

    # --- brand / gear set lookups ------------------------------------------

    def brand_set(self, name: str):
        return self._brand_set_by_name.get(name)

    def gear_set(self, name: str):
        return self._gear_set_by_name.get(name)

    # --- attribute lookups -------------------------------------------------

    def attribute_by_id(self, attr_id: str):
        return self._attribute_by_id.get(attr_id)

    def attributes_for_pool(self, pool: str) -> list:
        """All attributes whose compatibility list includes `pool`."""
        return [a for a in self.attributes if pool in a.compatibility]

    def attributes_for_stat(self, stat_id: str) -> list:
        """All attribute rows with the given stat_id (may span multiple pools/categories)."""
        return self._attribute_by_stat_id.get(stat_id, [])

    # --- resolve slot value ------------------------------------------------

    def resolve_weapon_mods(self, slot_value, category: str) -> list:
        """Return eligible WeaponMod objects for a weapon attachment SlotValue.

        type:{pool}  → all mods in that category whose compatibility includes pool
        fixed:{name} → the single named mod
        na           → []
        """
        if slot_value.is_empty:
            return []
        if slot_value.is_fixed:
            mod = self.mod_by_name(slot_value.value)
            return [mod] if mod else []
        return [m for m in self.mods_for_pool(slot_value.value) if m.category == category]

    def resolve_weapon_talent(self, slot_value) -> list:
        """Return eligible WeaponTalent objects for a weapon talent SlotValue."""
        if slot_value.is_empty:
            return []
        if slot_value.is_fixed:
            t = self.weapon_talent_by_name(slot_value.value)
            return [t] if t else []
        return self.talents_for_weapon_family(slot_value.value)

    def resolve_gear_talent(self, slot_value, slot_type: str) -> list:
        """Return eligible GearTalent objects for a gear piece talent SlotValue."""
        if slot_value.is_empty:
            return []
        if slot_value.is_fixed:
            t = self.gear_talent_by_name(slot_value.value)
            return [t] if t else []
        return self.talents_for_slot(slot_type)

    def __repr__(self) -> str:
        return (
            f"Catalog("
            f"weapon_mods={len(self.weapon_mods)}, "
            f"weapon_talents={len(self.weapon_talents)}, "
            f"gear_mods={len(self.gear_mods)}, "
            f"gear_talents={len(self.gear_talents)}, "
            f"brand_sets={len(self.brand_sets)}, "
            f"gear_sets={len(self.gear_sets)}, "
            f"attributes={len(self.attributes)})"
        )
