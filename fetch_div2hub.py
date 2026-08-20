"""
Description:
    Fetches all weapon, talent, gear, and attribute CSV files from the div2hub/game-data
    GitHub repository and saves them to the data lake Bronze layer. Existing files are
    versioned rather than overwritten (appends _v2, _v3, etc.). Writes a run log to 00_Logs.

Source Data:
    GitHub raw CSVs from https://raw.githubusercontent.com/div2hub/game-data/main/weapons/
    GitHub raw CSVs from https://raw.githubusercontent.com/div2hub/game-data/main/gear/
    GitHub raw CSV  from https://raw.githubusercontent.com/div2hub/game-data/main/attributes.csv

Outputs:
    data-lake/01_Bronze/division_2/{YYYYMMDD}_ext_weapons_{type}.csv
    data-lake/01_Bronze/division_2/{YYYYMMDD}_ext_gear_{type}.csv
    data-lake/01_Bronze/division_2/{YYYYMMDD}_ext_attributes_all.csv
    data-lake/00_Logs/division_2/fetch_div2hub_{YYYYMMDD}.log
"""

import urllib.request
import os
import re
from datetime import datetime

ROOT_BASE = "https://raw.githubusercontent.com/div2hub/game-data/main/"
WEAPONS_BASE = ROOT_BASE + "weapons/"
GEAR_BASE = ROOT_BASE + "gear/"

ROOT_FILES = {
    "attributes": "attributes.csv",
}

WEAPON_FILES = {
    "assault_rifles": "assault_rifles.csv",
    "smgs": "smgs.csv",
    "lmgs": "lmgs.csv",
    "rifles": "rifles.csv",
    "mmrs": "mmrs.csv",
    "shotguns": "shotguns.csv",
    "pistols": "pistols.csv",
    "talents": "weapon_talents.csv",
    "mods": "weapon_mods.csv",
}

GEAR_FILES = {
    "masks": "masks.csv",
    "backpacks": "backpacks.csv",
    "chests": "chests.csv",
    "gloves": "gloves.csv",
    "holsters": "holsters.csv",
    "knees": "knees.csv",
    "brand_sets": "brand_sets.csv",
    "gear_sets": "gear_sets.csv",
    "gear_talents": "gear_talents.csv",
    "gear_mods": "gear_mods.csv",
}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BRONZE_DIR = os.path.normpath(
    os.path.join(SCRIPT_DIR, "..", "data-lake", "01_Bronze", "division_2")
)
LOG_DIR = os.path.normpath(
    os.path.join(SCRIPT_DIR, "..", "data-lake", "00_Logs", "division_2")
)


def _versioned_path(dest: str) -> str:
    """Return dest unchanged if it does not exist; otherwise increment _vN suffix."""
    if not os.path.exists(dest):
        return dest
    base, ext = os.path.splitext(dest)
    version = 2
    match = re.search(r"_v(\d+)$", base)
    if match:
        version = int(match.group(1)) + 1
        base = base[: match.start()]
    while True:
        candidate = f"{base}_v{version}{ext}"
        if not os.path.exists(candidate):
            return candidate
        version += 1


def _fetch_single(url: str, dest_name: str, run_date: str) -> list:
    """Fetch one file with an explicit destination name and return log lines."""
    dest = os.path.join(BRONZE_DIR, f"{run_date}_{dest_name}")
    dest = _versioned_path(dest)
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            content = response.read().decode("utf-8")
        with open(dest, "w", encoding="utf-8", newline="") as f:
            f.write(content)
        msg = f"  OK  {os.path.basename(dest)}"
    except Exception as exc:
        msg = f"  ERR {dest_name}: {exc}"
    print(msg)
    return [f"\n--- attributes ---\n", msg + "\n"]


def _fetch_group(base_url: str, files: dict, category: str, run_date: str) -> list:
    """Fetch one group of files and return log lines."""
    log_lines = [f"\n--- {category} ---\n"]
    for label, filename in files.items():
        url = base_url + filename
        dest = os.path.join(BRONZE_DIR, f"{run_date}_ext_{category}_{label}.csv")
        dest = _versioned_path(dest)
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                content = response.read().decode("utf-8")
            with open(dest, "w", encoding="utf-8", newline="") as f:
                f.write(content)
            msg = f"  OK  {os.path.basename(dest)}"
        except Exception as exc:
            msg = f"  ERR {filename}: {exc}"
        print(msg)
        log_lines.append(msg + "\n")
    return log_lines


def fetch_all():
    os.makedirs(BRONZE_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)

    run_date = datetime.now().strftime("%Y%m%d")
    log_lines = [f"fetch_div2hub — run date: {run_date}\n"]

    log_lines += _fetch_single(ROOT_BASE + "attributes.csv", "ext_attributes_all.csv", run_date)
    log_lines += _fetch_group(WEAPONS_BASE, WEAPON_FILES, "weapons", run_date)
    log_lines += _fetch_group(GEAR_BASE, GEAR_FILES, "gear", run_date)

    log_path = os.path.join(LOG_DIR, f"fetch_div2hub_{run_date}.log")
    with open(log_path, "w", encoding="utf-8") as f:
        f.writelines(log_lines)
    print(f"\nLog saved: {log_path}")


if __name__ == "__main__":
    fetch_all()
