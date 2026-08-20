# TD2 Analysis Ideas

Tracks planned analyses for the Division 2 weapon/gear project. Add new ideas at the bottom; update status as work progresses.

**Status values**: `planned` · `in-progress` · `complete` · `blocked`

---

## Idea 1 — Weapon Comparison Within a Type

**Status**: `in-progress`

**Goal**: Given a weapon family (e.g. assault rifles), rank all weapons by DPS and surface the best option.

**Approach**:
- Load the weapon-type CSV (e.g. `assault_rifles.csv`)
- Compute a DPS score per weapon:
  - Raw DPS: `base_damage × (base_rpm / mag_size)`
  - Sustained DPS: weight by `base_mag_size / base_reload_time`
  - Headshot build variant: apply `hsd` multiplier
- Resolve `fixed:` attachment slots via `weapon_mods.name` and `fixed:` talent slots via `weapon_talents.name` before scoring named/exotic weapons
- Output: ranked table with key stats and score per weapon

**Data needed**: weapon-type file + `weapon_mods` + `weapon_talents`

**Notes**: Most self-contained of the three analyses. Good starting point for validating the DPS scoring model that underlies ideas 2 and 3.

---

## Idea 2 — Brand Set Optimizer (Gear Around a Weapon Loadout)

**Status**: `complete`

**Goal**: Given one or two weapon types, find the best brand set combination across all 6 gear slots to maximize weapon-relevant stat bonuses.

**Context**: The user typically runs two different weapon types (e.g. MMR + shotgun) and mixes brands up to 3 pieces of any one brand (2-2-2, 3-2-1, or 3-3 patterns). Chest and backpack talents are a playstyle decision handled separately in Idea 5 — this optimizer focuses purely on brand bonuses and gear cores.

**Approach**:
- Parse all brand bonus strings (`1pc_bonus`, `2pc_bonus`, `3pc_bonus`) from `brand_sets`
- Score each brand's bonuses against a priority list derived from the input weapon types:
  1. `weapon-damage` flat (benefits both weapons)
  2. `headshot-damage` (strong for MMRs and headshot builds)
  3. Weapon-type-specific damage (e.g. `marksman-rifle-damage`, `shotgun-damage`) — lower priority since only active per weapon
  4. `critical-hit-chance` / `critical-hit-damage` (universal offensive)
- Enumerate brand combinations across the 6 gear slots (mask, backpack, chest, gloves, holster, knees) for each pattern (2-2-2, 3-2-1, 3-3)
- Rank combinations by total weighted bonus score
- Also flag brands whose `default_core_stat_id` is `weapon-damage` — preferred over armor or skill-tier for offensive builds
- Output: ranked brand combinations per pattern, with per-slot assignment and total bonus summary

**Data needed**: `brand_sets` + `attributes`

**Notes**:
- Chest and backpack talent selection is deliberately excluded — see Idea 5
- Named/exotic gear pieces with locked cores/brands are not modeled here (that requires inventory data — see Idea 3)
- If both input weapons are the same type, type-specific bonuses score the same as flat weapon-damage

**Blocked by**: nothing — can build now

---

## Idea 3 — Gear Audit and Upgrade Path

**Status**: `blocked`

**Goal**: Given a player's current gear, score the loadout and identify the highest-impact improvements.

**Approach**:
- Score active brand bonus thresholds (1/2/3pc) via `brand_sets`
- Score active gear set bonus thresholds (2/3/4pc) via `gear_sets`
- Flag sub-optimal core types (e.g. armor core on an offensive build)
- Identify open or low-value mod slots and recommend replacements from `gear_mods`
- Recommend which single gear piece to swap to unlock the next bonus tier
- Output: scored summary of current loadout + prioritized upgrade list

**Data needed**: all reference tables + **user's current gear as input** (not yet defined)

**Blocked by**: Input layer — need to define how the player's current gear is described (manual CSV? item names?). The reference tables are all in place; only the input format is missing.

---

## Idea 5 — Chest and Backpack Talent Recommender

**Status**: `planned`

**Goal**: Given a playstyle or build direction, surface the best chest and backpack talents and explain the tradeoffs between them.

**Context**: Chest and backpack talents are independent of weapon type and brand choice — they stack on top of whatever gear build you run. The right talent depends heavily on how you play: aggressive vs. cautious, solo vs. group, crit-focused vs. headshot-focused, skill-heavy vs. pure weapon. This is a recommendation tool, not a strict optimizer.

**Approach**:
- Load `gear_talents` and split by `compatibility` (chest vs. backpack)
- Classify each talent by primary benefit category:
  - **Weapon damage amp** — flat % boost to total weapon damage (e.g. `Gunslinger`, `Vigilance`, `Obliterate`)
  - **Headshot / crit** — rewards precise play (e.g. `Headhunter`, `Concussion`)
  - **Sustain / survival** — armor, repairs, on-kill effects (e.g. `Bloodsucker`, `Unbreakable`)
  - **Skill synergy** — rewards mixed weapon+skill builds (e.g. `Combined Arms`, `Tech Support`)
  - **Team / support** — buffs allies (e.g. `Leadership`, `Overwatch`)
- For each playstyle input (e.g. "solo DPS", "headshot build", "aggressive"), return the top 3 chest + top 3 backpack talents with a plain-English explanation of when each shines and what its downside is
- Flag perfect variants and note they require a named/exotic piece to access

**Data needed**: `gear_talents`

**Notes**:
- Talent value is highly situational — the output should frame options and tradeoffs, not declare a single winner
- Perfect talents (compatibility = N/A) set the ceiling; their base variants are the tinkerable equivalent
- Pairs naturally with Idea 2 output: once you have a brand combo, pick the chest/backpack talents that match how you intend to use it

---

## Idea 4 — Weapon Talent Analysis (Best Talent Per Weapon Type)

**Status**: `planned`

**Goal**: Determine the best weapon talents for each weapon type (assault rifle, SMG, LMG, etc.) so that when tinkering, there's a clear recommendation for what to roll.

**Background**: Base weapons can have any talent from their pool swapped in via tinkering. Named/exotic weapons have locked talents. The talent pool varies by weapon compatibility — some talents are universal (available on all weapon types), others are restricted. Talents are situational (crit build vs. headshot build vs. sustain), so the analysis should bucket recommendations by playstyle.

**Approach**:
- Load `weapon_talents` and filter by `compatibility` to get the eligible pool per weapon type (e.g. `assault-rifle`)
- Classify each talent by its primary benefit:
  - **Damage amp** — increases weapon damage by a flat or conditional %
  - **Crit** — boosts CHC or CHD
  - **Headshot** — boosts headshot damage
  - **Sustain** — benefits reload, magazine, or on-kill effects
  - **Utility** — swap speed, armor, skill interaction
- Score or rank within each class: named/perfect variants score above base variants
- Cross-reference with weapon type to highlight which talent classes are most commonly available per weapon family
- Output: per-weapon-type talent tier list, bucketed by playstyle

**Data needed**: `weapon_talents` + weapon-type CSVs (for `talent_slot` pool key)

**Notes**:
- Perfect talents (compatibility = N/A) are locked to named/exotic weapons and should be noted as a benchmark — they set the ceiling for what a base talent can approximate
- Talent scoring is inherently qualitative (conditional triggers, team vs. solo, boss vs. trash) — the initial output should organize and surface the options clearly rather than assign a single numeric score
- This analysis informs tinkering decisions and pairs naturally with Idea 1 (weapon comparison) to give a complete "platform + talent" recommendation
