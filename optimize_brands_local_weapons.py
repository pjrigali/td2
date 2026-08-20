"""
Description:
    Given one or two weapon types, scores all 38 brand sets by their bonus
    relevance to those weapons and enumerates the top brand combinations for
    three mixing patterns: 3-3 (two brands), 3-2-1 (three brands, max 3pc),
    and 2-2-2 (three brands, equal mix). Brands with a weapon-damage core get
    a bonus since their core slots align with an offensive build.
    Chest and backpack talents are intentionally excluded — see Idea 5.

Source Data:
    data-lake/01_Bronze/division_2/*_ext_gear_brand_sets.csv

Outputs:
    stdout: scored brand table + top combos per pattern
    data-lake/02_Silver/division_2/{YYYYMMDD}_local_brands_{types}_optimized.csv
"""

from __future__ import annotations
import csv
import itertools
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from loader import load_brand_sets, load_gear_sets

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SILVER_DIR = os.path.normpath(
    os.path.join(SCRIPT_DIR, "..", "data-lake", "02_Silver", "division_2")
)

VALID_TYPES = {"assault_rifles", "smgs", "lmgs", "rifles", "mmrs", "shotguns", "pistols"}

TOP_N = 10

# ---------------------------------------------------------------------------
# Stat weights
# ---------------------------------------------------------------------------

# Base weights applied to every build regardless of weapon type
BASE_WEIGHTS: dict[str, float] = {
    "weapon-damage":        10.0,
    "headshot-damage":       8.0,
    "critical-hit-chance":   6.0,
    "critical-hit-damage":   6.0,
    "damage-to-armor":       3.0,
    "health-damage":         3.0,
    "rate-of-fire":          2.0,
    "magazine-size":         2.0,
    "reload-speed":          2.0,
    "weapon-handling":       2.0,
    "optimal-range":         1.5,
    "accuracy":              1.5,
    "stability":             1.0,
    "ammo-capacity":         1.0,
}

# Additional weights added per input weapon type
TYPE_WEIGHTS: dict[str, dict[str, float]] = {
    "mmrs":           {"marksman-rifle-damage": 8.0, "headshot-damage": 3.0},
    "shotguns":       {"shotgun-damage": 8.0},
    "assault_rifles": {"assault-rifle-damage": 8.0},
    "smgs":           {"smg-damage": 8.0},
    "lmgs":           {"lmg-damage": 8.0},
    "rifles":         {"rifle-damage": 8.0},
    "pistols":        {"pistol-damage": 8.0},
}

# Bonus added per piece from a weapon-damage core brand (offensive core alignment)
CORE_BONUS = {"weapon-damage": 5.0, "armor": 0.0, "skill-tier": 0.0}


# ---------------------------------------------------------------------------
# Bonus parsing
# ---------------------------------------------------------------------------

def _parse_tier(tier_str: str) -> list[tuple[str, float]]:
    """Parse one bonus tier string into (stat_name, value) pairs.

    'stat:headshot-damage:13%|stat:marksman-rifle-damage:24%'
    → [('headshot-damage', 13.0), ('marksman-rifle-damage', 24.0)]
    """
    results = []
    if not tier_str or tier_str.strip() == "N/A":
        return results
    for part in tier_str.split("|"):
        part = part.strip()
        if not part.startswith("stat:"):
            continue
        remainder = part[5:]
        idx = remainder.rfind(":")
        if idx == -1:
            continue
        stat_name = remainder[:idx]
        val_str = remainder[idx + 1:].replace("%", "").strip()
        try:
            results.append((stat_name, float(val_str)))
        except ValueError:
            continue
    return results


def _score_tier(tier_str: str, weights: dict[str, float]) -> float:
    return sum(val * weights.get(stat, 0.0) for stat, val in _parse_tier(tier_str))


def _tier_label(tier_str: str) -> str:
    """Human-readable summary of a bonus tier."""
    parts = _parse_tier(tier_str)
    if not parts:
        return "—"
    return "  +  ".join(f"{stat}: {val:g}%" for stat, val in parts)


# ---------------------------------------------------------------------------
# Brand scoring
# ---------------------------------------------------------------------------

def build_weights(weapon_types: list[str]) -> dict[str, float]:
    weights = dict(BASE_WEIGHTS)
    for wt in weapon_types:
        for stat, bonus in TYPE_WEIGHTS.get(wt, {}).items():
            weights[stat] = weights.get(stat, 0.0) + bonus
    return weights


def score_brands(weapon_types: list[str]) -> list[dict]:
    weights = build_weights(weapon_types)
    brands = load_brand_sets()
    scored = []
    for b in brands:
        core_per_piece = CORE_BONUS.get(b.default_core_stat_id, 0.0)
        s1 = _score_tier(b.bonus_1pc, weights) + core_per_piece
        s2 = s1 + _score_tier(b.bonus_2pc, weights) + core_per_piece
        s3 = s2 + _score_tier(b.bonus_3pc, weights) + core_per_piece
        scored.append({
            "brand":   b,
            "score_1": s1,
            "score_2": s2,
            "score_3": s3,
        })
    return sorted(scored, key=lambda x: x["score_3"], reverse=True)


def score_gear_sets(weapon_types: list[str]) -> list[dict]:
    """Score gear sets up to 3pc only — 4pc bonuses involve mechanics too
    situational to quantify (transformation effects, cooldown resets, etc.)."""
    weights = build_weights(weapon_types)
    sets = load_gear_sets()
    scored = []
    for gs in sets:
        core_per_piece = CORE_BONUS.get(gs.default_core_stat_id, 0.0)
        # Gear sets typically have no 1pc bonus; scoring starts at 2pc
        s2 = _score_tier(gs.bonus_2pc, weights) + 2 * core_per_piece
        s3 = s2 + _score_tier(gs.bonus_3pc, weights) + core_per_piece
        scored.append({
            "gear_set": gs,
            "score_2":  s2,
            "score_3":  s3,
        })
    return sorted(scored, key=lambda x: x["score_3"], reverse=True)


# ---------------------------------------------------------------------------
# Combination enumeration
# ---------------------------------------------------------------------------

def _combo_score(entries: list[dict], counts: list[int]) -> float:
    total = 0.0
    for entry, n in zip(entries, counts):
        key = f"score_{n}"
        total += entry[key]
    return total


def _combo_label(entries: list[dict], counts: list[int]) -> str:
    return " | ".join(
        f"{e['brand'].name} ×{n}" for e, n in zip(entries, counts)
    )


def top_combos(scored: list[dict], pattern: str, top_n: int = TOP_N) -> list[dict]:
    """Return top_n brand combinations for the given pattern."""
    results = []

    if pattern == "3-3":
        for a, b in itertools.combinations(scored, 2):
            score = a["score_3"] + b["score_3"]
            results.append({
                "pattern": pattern,
                "score":   round(score, 1),
                "label":   _combo_label([a, b], [3, 3]),
                "brands":  [(a["brand"].name, 3, a["brand"].default_core_stat_id),
                            (b["brand"].name, 3, b["brand"].default_core_stat_id)],
            })

    elif pattern == "3-2-1":
        for a, b, c in itertools.permutations(scored, 3):
            score = a["score_3"] + b["score_2"] + c["score_1"]
            results.append({
                "pattern": pattern,
                "score":   round(score, 1),
                "label":   _combo_label([a, b, c], [3, 2, 1]),
                "brands":  [(a["brand"].name, 3, a["brand"].default_core_stat_id),
                            (b["brand"].name, 2, b["brand"].default_core_stat_id),
                            (c["brand"].name, 1, c["brand"].default_core_stat_id)],
            })

    elif pattern == "2-2-2":
        for a, b, c in itertools.combinations(scored, 3):
            score = a["score_2"] + b["score_2"] + c["score_2"]
            results.append({
                "pattern": pattern,
                "score":   round(score, 1),
                "label":   _combo_label([a, b, c], [2, 2, 2]),
                "brands":  [(a["brand"].name, 2, a["brand"].default_core_stat_id),
                            (b["brand"].name, 2, b["brand"].default_core_stat_id),
                            (c["brand"].name, 2, c["brand"].default_core_stat_id)],
            })

    elif pattern == "2-2-1-1":
        for four in itertools.combinations(scored, 4):
            # For each set of 4 brands, find the optimal assignment of which 2 get 2pc
            best_score = -1.0
            best_counts = None
            for two_idx in itertools.combinations(range(4), 2):
                counts = [2 if i in two_idx else 1 for i in range(4)]
                score = sum(four[i][f"score_{counts[i]}"] for i in range(4))
                if score > best_score:
                    best_score = score
                    best_counts = counts
            entries = list(four)
            results.append({
                "pattern": pattern,
                "score":   round(best_score, 1),
                "label":   _combo_label(entries, best_counts),
                "brands":  [(entries[i]["brand"].name, best_counts[i], entries[i]["brand"].default_core_stat_id)
                            for i in range(4)],
            })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_n]


def top_gs_combos(
    gs_scored: list[dict],
    brand_scored: list[dict],
    pattern: str,
    top_n: int = TOP_N,
) -> list[dict]:
    """Return top_n combinations that anchor on a gear set (up to 3pc) + brands.

    Patterns:
        GS2+2+2  — 2pc gear set + 2 brands × 2pc  (6 slots)
        GS2+3+1  — 2pc gear set + 1 brand × 3pc + 1 brand × 1pc  (6 slots)
        GS3+3    — 3pc gear set + 1 brand × 3pc  (6 slots)
        GS3+2+1  — 3pc gear set + 1 brand × 2pc + 1 brand × 1pc  (6 slots)
    """
    results = []

    if pattern == "GS2+2+2":
        for gs in gs_scored:
            for a, b in itertools.combinations(brand_scored, 2):
                score = gs["score_2"] + a["score_2"] + b["score_2"]
                results.append({
                    "pattern": pattern,
                    "score":   round(score, 1),
                    "label":   f"[GS] {gs['gear_set'].name} ×2 | {_combo_label([a, b], [2, 2])}",
                    "brands":  [
                        (gs["gear_set"].name, 2, gs["gear_set"].default_core_stat_id),
                        (a["brand"].name, 2, a["brand"].default_core_stat_id),
                        (b["brand"].name, 2, b["brand"].default_core_stat_id),
                    ],
                })

    elif pattern == "GS2+3+1":
        for gs in gs_scored:
            for a, b in itertools.permutations(brand_scored, 2):
                score = gs["score_2"] + a["score_3"] + b["score_1"]
                results.append({
                    "pattern": pattern,
                    "score":   round(score, 1),
                    "label":   f"[GS] {gs['gear_set'].name} ×2 | {_combo_label([a, b], [3, 1])}",
                    "brands":  [
                        (gs["gear_set"].name, 2, gs["gear_set"].default_core_stat_id),
                        (a["brand"].name, 3, a["brand"].default_core_stat_id),
                        (b["brand"].name, 1, b["brand"].default_core_stat_id),
                    ],
                })

    elif pattern == "GS3+3":
        for gs in gs_scored:
            for a in brand_scored:
                score = gs["score_3"] + a["score_3"]
                results.append({
                    "pattern": pattern,
                    "score":   round(score, 1),
                    "label":   f"[GS] {gs['gear_set'].name} ×3 | {_combo_label([a], [3])}",
                    "brands":  [
                        (gs["gear_set"].name, 3, gs["gear_set"].default_core_stat_id),
                        (a["brand"].name, 3, a["brand"].default_core_stat_id),
                    ],
                })

    elif pattern == "GS3+2+1":
        for gs in gs_scored:
            for a, b in itertools.permutations(brand_scored, 2):
                score = gs["score_3"] + a["score_2"] + b["score_1"]
                results.append({
                    "pattern": pattern,
                    "score":   round(score, 1),
                    "label":   f"[GS] {gs['gear_set'].name} ×3 | {_combo_label([a, b], [2, 1])}",
                    "brands":  [
                        (gs["gear_set"].name, 3, gs["gear_set"].default_core_stat_id),
                        (a["brand"].name, 2, a["brand"].default_core_stat_id),
                        (b["brand"].name, 1, b["brand"].default_core_stat_id),
                    ],
                })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_n]


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def print_brand_scores(scored: list[dict]) -> None:
    print(f"\n{'Brand':<32} {'Core':<15} {'1pc':>7} {'2pc':>7} {'3pc':>7}  Bonuses (relevant)")
    print("-" * 110)
    for row in scored[:20]:
        b = row["brand"]
        bonuses = []
        for tier in [b.bonus_1pc, b.bonus_2pc, b.bonus_3pc]:
            parts = _parse_tier(tier)
            bonuses.append(", ".join(f"{s}:{v:g}%" for s, v in parts) if parts else "—")
        print(
            f"{b.name:<32} {b.default_core_stat_id:<15}"
            f" {row['score_1']:>7.1f} {row['score_2']:>7.1f} {row['score_3']:>7.1f}"
            f"  {' | '.join(bonuses)}"
        )
    print(f"\n  (showing top 20 of {len(scored)} brands by 3pc score)")


def print_gear_set_scores(gs_scored: list[dict]) -> None:
    print(f"\n{'Gear Set':<36} {'Core':<15} {'2pc':>7} {'3pc':>7}  2pc bonus / 3pc bonus")
    print("-" * 100)
    for row in gs_scored[:15]:
        gs = row["gear_set"]
        b2 = _tier_label(gs.bonus_2pc)
        b3 = _tier_label(gs.bonus_3pc)
        print(
            f"{gs.name:<36} {gs.default_core_stat_id:<15}"
            f" {row['score_2']:>7.1f} {row['score_3']:>7.1f}"
            f"  {b2} / {b3}"
        )
    print(f"\n  (showing top 15 of {len(gs_scored)} gear sets by 3pc score, 4pc excluded)")


def print_combos(combos: list[dict], pattern: str) -> None:
    print(f"\n--- Pattern {pattern} ---")
    for i, c in enumerate(combos, 1):
        core_flags = [f"[{b[2][:3]}]" for b in c["brands"]]
        print(f"  {i:>2}. Score {c['score']:>7.1f}  {c['label']}  cores: {' '.join(core_flags)}")


# ---------------------------------------------------------------------------
# Save to Silver
# ---------------------------------------------------------------------------

def save_silver(
    weapon_types: list[str],
    scored: list[dict],
    all_combos: dict[str, list[dict]],
) -> str:
    os.makedirs(SILVER_DIR, exist_ok=True)
    run_date = datetime.now().strftime("%Y%m%d")
    types_tag = "_".join(weapon_types)
    path = os.path.join(SILVER_DIR, f"{run_date}_local_brands_{types_tag}_optimized.csv")

    rows = []
    for pattern, combos in all_combos.items():
        for rank, c in enumerate(combos, 1):
            rows.append({
                "rank":        rank,
                "pattern":     c["pattern"],
                "score":       c["score"],
                "combo":       c["label"],
                "weapon_types": "+".join(weapon_types),
            })

    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["rank", "pattern", "score", "combo", "weapon_types"])
        writer.writeheader()
        writer.writerows(rows)
    return path


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    weapon_types = sys.argv[1:] if len(sys.argv) > 1 else ["mmrs", "shotguns"]

    invalid = [wt for wt in weapon_types if wt not in VALID_TYPES]
    if invalid:
        print(f"Unknown weapon type(s): {invalid}")
        print(f"Valid types: {sorted(VALID_TYPES)}")
        sys.exit(1)

    print(f"\n=== Brand Set Optimizer ===")
    print(f"Weapon types: {', '.join(weapon_types)}")

    scored = score_brands(weapon_types)
    print_brand_scores(scored)

    gs_scored = score_gear_sets(weapon_types)
    print_gear_set_scores(gs_scored)

    patterns = ["3-3", "3-2-1", "2-2-2", "2-2-1-1"]
    all_combos: dict[str, list[dict]] = {}
    for pattern in patterns:
        combos = top_combos(scored, pattern)
        all_combos[pattern] = combos
        print_combos(combos, pattern)

    gs_patterns = ["GS2+2+2", "GS2+3+1", "GS3+3", "GS3+2+1"]
    for pattern in gs_patterns:
        combos = top_gs_combos(gs_scored, scored, pattern)
        all_combos[pattern] = combos
        print_combos(combos, pattern)

    path = save_silver(weapon_types, scored, all_combos)
    print(f"\nSaved: {path}")
