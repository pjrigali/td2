"""
Description:
    Data model classes for Division 2 weapons, gear pieces, and player profiles.
    SlotValue parses the type/fixed/N/A encoding used across all item columns.
    Weapon and GearPiece load directly from Bronze layer CSV rows.
    Profile assembles a full six-piece gear loadout plus up to three weapons.

Source Data:
    Instances are populated from data-lake/01_Bronze/division_2/ CSV files.

Outputs:
    Module — import Weapon, GearPiece, Profile, SlotValue into analysis scripts.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


GEAR_SLOTS = ("mask", "backpack", "chest", "gloves", "holster", "knees")
WEAPON_CLASSES = ("assault_rifles", "smgs", "lmgs", "rifles", "mmrs", "shotguns", "pistols")
ATTACHMENT_SLOTS = ("optics", "magazine", "muzzle", "underbarrel")


# ---------------------------------------------------------------------------
# Slot value
# ---------------------------------------------------------------------------

@dataclass
class SlotValue:
    """Parsed representation of any slot column value.

    kind:
        "type"  — random roll from pool; value is the pool key
        "fixed" — locked value (named/exotic); value is the exact name or stat id
        "na"    — slot does not exist on this item
    """
    kind: str
    value: str

    @classmethod
    def parse(cls, raw: str) -> SlotValue:
        raw = raw.strip()
        if not raw or raw == "N/A":
            return cls("na", "")
        if raw.startswith("type:"):
            return cls("type", raw[5:])
        if raw.startswith("fixed:"):
            return cls("fixed", raw[6:])
        return cls("na", "")

    @property
    def is_empty(self) -> bool:
        return self.kind == "na"

    @property
    def is_random(self) -> bool:
        return self.kind == "type"

    @property
    def is_fixed(self) -> bool:
        return self.kind == "fixed"

    def __str__(self) -> str:
        if self.kind == "na":
            return "N/A"
        return f"{self.kind}:{self.value}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _float(val: str, default: float = 0.0) -> float:
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _int(val: str, default: int = 0) -> int:
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _bool(val: str) -> bool:
    return val.strip().upper() == "TRUE"


# ---------------------------------------------------------------------------
# Weapon
# ---------------------------------------------------------------------------

@dataclass
class Weapon:
    """A single weapon item loaded from a weapon-class CSV row.

    weapon_class: file-level category (assault_rifles, smgs, lmgs, etc.)
    family:       weapon variant group from the CSV (ACR, M60, Aug, etc.)
    slot_type:    CSV slot_type column — typically "main" or "sidearm"
    hsd:          headshot damage bonus in percent (e.g. 55 means +55%)
    """
    name: str
    weapon_class: str
    family: str
    slot_type: str
    is_named: bool
    is_exotic: bool
    base_damage: float
    base_rpm: int
    base_mag_size: int
    base_reload_time: float
    optimal_range: int
    hsd: float
    optics: SlotValue
    magazine: SlotValue
    muzzle: SlotValue
    underbarrel: SlotValue
    talent_slot: SlotValue
    core_1: SlotValue
    core_2: SlotValue
    core_3: SlotValue
    minor_1: SlotValue
    minor_2: SlotValue
    minor_3: SlotValue

    # --- computed DPS properties -------------------------------------------

    @property
    def raw_dps(self) -> float:
        """Burst DPS: damage per trigger pull times rounds per second."""
        return self.base_damage * (self.base_rpm / 60)

    @property
    def sustained_dps(self) -> float:
        """DPS averaged across mag + reload cycle."""
        if self.base_reload_time <= 0 or self.base_rpm <= 0:
            return self.raw_dps
        shots_per_sec = self.base_rpm / 60
        mag_duration = self.base_mag_size / shots_per_sec
        cycle_time = mag_duration + self.base_reload_time
        return (self.base_damage * self.base_mag_size) / cycle_time

    @property
    def headshot_dps(self) -> float:
        """Sustained DPS scaled by the weapon's base headshot damage bonus."""
        return self.sustained_dps * (1 + self.hsd / 100)

    @property
    def has_base_stats(self) -> bool:
        """False for exotic placeholder rows with no numeric stats."""
        return self.base_damage > 0

    # --- attachment helpers -------------------------------------------------

    @property
    def attachment_slots(self) -> dict[str, SlotValue]:
        return {
            "optics": self.optics,
            "magazine": self.magazine,
            "muzzle": self.muzzle,
            "underbarrel": self.underbarrel,
        }

    @property
    def open_attachment_slots(self) -> list[str]:
        return [k for k, v in self.attachment_slots.items() if not v.is_empty]

    # --- loader -------------------------------------------------------------

    @classmethod
    def from_row(cls, row: dict, weapon_class: str) -> Weapon:
        return cls(
            name=row["name"],
            weapon_class=weapon_class,
            family=row.get("family", ""),
            slot_type=row.get("slot_type", "main"),
            is_named=_bool(row.get("is_named", "")),
            is_exotic=_bool(row.get("is_exotic", "")),
            base_damage=_float(row.get("base_damage", "")),
            base_rpm=_int(row.get("base_rpm", "")),
            base_mag_size=_int(row.get("base_mag_size", "")),
            base_reload_time=_float(row.get("base_reload_time", "")),
            optimal_range=_int(row.get("optimal_range", "")),
            hsd=_float(row.get("hsd", "")),
            optics=SlotValue.parse(row.get("optics", "N/A")),
            magazine=SlotValue.parse(row.get("magazine", "N/A")),
            muzzle=SlotValue.parse(row.get("muzzle", "N/A")),
            underbarrel=SlotValue.parse(row.get("underbarrel", "N/A")),
            talent_slot=SlotValue.parse(row.get("talent_slot", "N/A")),
            core_1=SlotValue.parse(row.get("core_1", "N/A")),
            core_2=SlotValue.parse(row.get("core_2", "N/A")),
            core_3=SlotValue.parse(row.get("core_3", "N/A")),
            minor_1=SlotValue.parse(row.get("minor_1", "N/A")),
            minor_2=SlotValue.parse(row.get("minor_2", "N/A")),
            minor_3=SlotValue.parse(row.get("minor_3", "N/A")),
        )

    def __repr__(self) -> str:
        flags = []
        if self.is_exotic:
            flags.append("exotic")
        elif self.is_named:
            flags.append("named")
        tag = f" [{', '.join(flags)}]" if flags else ""
        return f"Weapon({self.name!r}{tag}, class={self.weapon_class})"


# ---------------------------------------------------------------------------
# GearPiece
# ---------------------------------------------------------------------------

@dataclass
class GearPiece:
    """A single gear item loaded from a gear-slot CSV row.

    slot_type: which of the six gear slots this item occupies
    brand_set: brand name, or empty string for gear set pieces
    gear_set:  gear set name, or empty string if not a set piece
    """
    slot_type: str
    brand_set: str
    gear_set: str
    name: str
    is_named: bool
    is_exotic: bool
    core_1: SlotValue
    core_2: SlotValue
    core_3: SlotValue
    minor_1: SlotValue
    minor_2: SlotValue
    minor_3: SlotValue
    talent_slot: SlotValue
    mod_1: SlotValue
    mod_2: SlotValue
    mod_3: SlotValue

    # --- identity helpers --------------------------------------------------

    @property
    def is_set_piece(self) -> bool:
        return bool(self.gear_set)

    @property
    def is_brand_piece(self) -> bool:
        return bool(self.brand_set) and not self.is_set_piece

    @property
    def has_talent(self) -> bool:
        return not self.talent_slot.is_empty

    # --- slot helpers ------------------------------------------------------

    @property
    def core_slots(self) -> list[SlotValue]:
        return [s for s in (self.core_1, self.core_2, self.core_3) if not s.is_empty]

    @property
    def minor_slots(self) -> list[SlotValue]:
        return [s for s in (self.minor_1, self.minor_2, self.minor_3) if not s.is_empty]

    @property
    def mod_slots(self) -> list[SlotValue]:
        return [s for s in (self.mod_1, self.mod_2, self.mod_3) if not s.is_empty]

    # --- loader ------------------------------------------------------------

    @classmethod
    def from_row(cls, row: dict, slot_type: str) -> GearPiece:
        raw_gear_set = row.get("gear_set", "N/A")
        return cls(
            slot_type=slot_type,
            brand_set=row.get("brand_set", ""),
            gear_set="" if raw_gear_set == "N/A" else raw_gear_set,
            name=row["name"],
            is_named=_bool(row.get("is_named", "")),
            is_exotic=_bool(row.get("is_exotic", "")),
            core_1=SlotValue.parse(row.get("core_1", "N/A")),
            core_2=SlotValue.parse(row.get("core_2", "N/A")),
            core_3=SlotValue.parse(row.get("core_3", "N/A")),
            minor_1=SlotValue.parse(row.get("minor_1", "N/A")),
            minor_2=SlotValue.parse(row.get("minor_2", "N/A")),
            minor_3=SlotValue.parse(row.get("minor_3", "N/A")),
            talent_slot=SlotValue.parse(row.get("talent_slot", "N/A")),
            mod_1=SlotValue.parse(row.get("mod_1", "N/A")),
            mod_2=SlotValue.parse(row.get("mod_2", "N/A")),
            mod_3=SlotValue.parse(row.get("mod_3", "N/A")),
        )

    def __repr__(self) -> str:
        flags = []
        if self.is_exotic:
            flags.append("exotic")
        elif self.is_named:
            flags.append("named")
        tag = f" [{', '.join(flags)}]" if flags else ""
        identity = self.gear_set or self.brand_set or "unknown"
        return f"GearPiece({self.name!r}{tag}, slot={self.slot_type}, set={identity!r})"


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

@dataclass
class Profile:
    """A player's equipped loadout: up to three weapons and six gear pieces.

    Weapons:
        primary   — main slot weapon (AR, SMG, LMG, rifle, MMR, shotgun)
        secondary — second main slot weapon
        sidearm   — pistol slot

    Gear slots follow Division 2's six fixed slots: mask, backpack, chest,
    gloves, holster, knees.
    """
    primary: Optional[Weapon] = None
    secondary: Optional[Weapon] = None
    sidearm: Optional[Weapon] = None
    mask: Optional[GearPiece] = None
    backpack: Optional[GearPiece] = None
    chest: Optional[GearPiece] = None
    gloves: Optional[GearPiece] = None
    holster: Optional[GearPiece] = None
    knees: Optional[GearPiece] = None

    # --- collections -------------------------------------------------------

    @property
    def weapons(self) -> list[Weapon]:
        return [w for w in (self.primary, self.secondary, self.sidearm) if w]

    @property
    def gear(self) -> list[GearPiece]:
        return [g for g in (self.mask, self.backpack, self.chest, self.gloves, self.holster, self.knees) if g]

    # --- set / brand bonus counts -----------------------------------------

    @property
    def brand_counts(self) -> dict[str, int]:
        """Number of equipped pieces per brand."""
        counts: dict[str, int] = {}
        for piece in self.gear:
            if piece.brand_set:
                counts[piece.brand_set] = counts.get(piece.brand_set, 0) + 1
        return counts

    @property
    def set_counts(self) -> dict[str, int]:
        """Number of equipped pieces per gear set."""
        counts: dict[str, int] = {}
        for piece in self.gear:
            if piece.gear_set:
                counts[piece.gear_set] = counts.get(piece.gear_set, 0) + 1
        return counts

    @property
    def active_brand_bonuses(self) -> dict[str, int]:
        """Brands with at least one piece equipped (all grant a 1pc bonus in TD2)."""
        return {brand: count for brand, count in self.brand_counts.items() if count >= 1}

    @property
    def active_set_bonuses(self) -> dict[str, int]:
        """Gear sets with at least the 2pc threshold met."""
        return {gs: count for gs, count in self.set_counts.items() if count >= 2}

    # --- slot management --------------------------------------------------

    def equip_gear(self, piece: GearPiece) -> None:
        """Place a gear piece into its slot, replacing whatever was there."""
        if piece.slot_type in GEAR_SLOTS:
            setattr(self, piece.slot_type, piece)

    def equipped_gear_slots(self) -> list[str]:
        return [s for s in GEAR_SLOTS if getattr(self, s) is not None]

    def missing_gear_slots(self) -> list[str]:
        return [s for s in GEAR_SLOTS if getattr(self, s) is None]

    def is_complete(self) -> bool:
        """True when all six gear slots and at least a primary weapon are filled."""
        return len(self.missing_gear_slots()) == 0 and self.primary is not None

    # --- summary ----------------------------------------------------------

    def summary(self) -> str:
        lines = ["=== Profile ==="]
        lines.append(f"Primary:   {self.primary or '—'}")
        lines.append(f"Secondary: {self.secondary or '—'}")
        lines.append(f"Sidearm:   {self.sidearm or '—'}")
        lines.append("")
        for slot in GEAR_SLOTS:
            piece = getattr(self, slot)
            lines.append(f"{slot.capitalize():10}: {piece or '—'}")
        lines.append("")
        if self.brand_counts:
            lines.append("Brands: " + ", ".join(f"{b} x{n}" for b, n in sorted(self.brand_counts.items())))
        if self.set_counts:
            lines.append("Sets:   " + ", ".join(f"{s} x{n}" for s, n in sorted(self.set_counts.items())))
        return "\n".join(lines)

    def __repr__(self) -> str:
        gear_filled = len(self.equipped_gear_slots())
        return f"Profile(weapons={len(self.weapons)}, gear={gear_filled}/6)"


# ---------------------------------------------------------------------------
# Reference table models
# ---------------------------------------------------------------------------

@dataclass
class WeaponMod:
    """One row from weapon_mods.csv.

    compatibility: pool keys this mod can appear in (empty list = named/exotic-specific only)
    stats:         parsed stat bonuses, e.g. {"headshot-damage": "30%", "reload-speed": "-10%"}
    """
    name: str
    category: str
    compatibility: list
    stats: dict

    def fits(self, pool: str) -> bool:
        """True if this mod is eligible for a slot with the given pool key."""
        return pool in self.compatibility


@dataclass
class WeaponTalent:
    """One row from weapon_talents.csv.

    compatibility: weapon families this talent can roll on (empty = perfect/exotic-locked)
    """
    name: str
    compatibility: list
    description: str

    def fits(self, family: str) -> bool:
        return family in self.compatibility

    @property
    def is_perfect(self) -> bool:
        return not self.compatibility


@dataclass
class GearMod:
    """One row from gear_mods.csv."""
    id: str
    stat_id: str
    range_min: str
    range_max: str
    compatibility: list
    category: str
    fidelity: str


@dataclass
class GearTalent:
    """One row from gear_talents.csv.

    compatibility: ["chest"], ["backpack"], or [] for perfect/exotic-locked talents
    """
    name: str
    compatibility: list
    description: str

    def fits(self, slot_type: str) -> bool:
        return slot_type in self.compatibility

    @property
    def is_perfect(self) -> bool:
        return not self.compatibility


@dataclass
class BrandSet:
    """One row from brand_sets.csv."""
    name: str
    default_core_stat_id: str
    bonus_1pc: str
    bonus_2pc: str
    bonus_3pc: str


@dataclass
class GearSet:
    """One row from gear_sets.csv."""
    name: str
    default_core_stat_id: str
    bonus_1pc: str
    bonus_2pc: str
    bonus_3pc: str
    bonus_4pc: str


@dataclass
class Attribute:
    """One row from attributes.csv.

    compatibility: stat pools this attribute can appear in (e.g. ["weapon-minor", "weapon-offensive-minor"])
                   empty list = named/exotic-specific fixed stat
    """
    id: str
    stat_id: str
    range_min: str
    range_max: str
    proto_max: str
    compatibility: list
    category: str
    fidelity: str

    @property
    def is_named_fixed(self) -> bool:
        return not self.compatibility
