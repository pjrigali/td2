"""
Description:
    Fetches all weapon and talent CSV files from the div2hub/game-data GitHub repository
    and saves them to the data lake Bronze layer. Existing files are versioned rather
    than overwritten (appends _v2, _v3, etc.).

Source Data:
    GitHub raw CSVs from https://raw.githubusercontent.com/div2hub/game-data/main/weapons/

Outputs:
    data-lake/01_Bronze/division_2/2026_ext_weapons_{type}.csv
    One file per weapon category: assault_rifles, smgs, lmgs, rifles, mmrs, shotguns, pistols, talents
"""

import urllib.request
import os
import re
from datetime import datetime

BASE_URL = "https://raw.githubusercontent.com/div2hub/game-data/main/weapons/"

FILES = {
    "assault_rifles": "assault_rifles.csv",
    "smgs": "smgs.csv",
    "lmgs": "lmgs.csv",
    "rifles": "rifles.csv",
    "mmrs": "mmrs.csv",
    "shotguns": "shotguns.csv",
    "pistols": "pistols.csv",
    "talents": "weapon_talents.csv",
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


def fetch_all():
    os.makedirs(BRONZE_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)

    run_date = datetime.now().strftime("%Y%m%d")
    log_lines = [f"fetch_weapons_div2hub — run date: {run_date}\n"]

    for label, filename in FILES.items():
        url = BASE_URL + filename
        dest = os.path.join(BRONZE_DIR, f"{run_date}_ext_weapons_{label}.csv")
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

    log_path = os.path.join(LOG_DIR, f"fetch_weapons_{run_date}.log")
    with open(log_path, "w", encoding="utf-8") as f:
        f.writelines(log_lines)
    print(f"\nLog saved: {log_path}")


if __name__ == "__main__":
    fetch_all()
