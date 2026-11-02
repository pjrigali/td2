# Division 2 Inventory Screen Scanner: Project Plan

## Overview
A safe, OCR-based inventory scanner for *Tom Clancy's The Division 2* on PC (Steam/Ubisoft Connect). 

Because the game lacks an official inventory API and uses Easy Anti-Cheat (EAC), this tool uses non-intrusive screen capture and optical character recognition (OCR) rather than memory hooks or packet inspection. It captures screenshots of the gear inspection panel via a hotkey, parses the item stats, and reconciles the extracted data against the existing Division 2 catalog in `data-lake/01_Bronze/division_2/`.

---

## Architecture & Data Flow

```
┌─────────────────────────────────┐
│     In-Game Gear Inspection     │
└────────────────┬────────────────┘
                 │
                 ▼  [Hotkey: e.g. F9]
┌─────────────────────────────────┐
│     capture_gear_card.py        │  ──> Saves to td2/captures/raw/*.png
│   (mss / Pillow + winsound)     │
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│   parse_inventory_images.py     │
│   ├─ 1. Bounding Box Crop (ROI) │
│   ├─ 2. Local OCR (EasyOCR/Tess)│
│   ├─ 3. Fuzzy Match via         │
│   │     td2/loader.py (Catalog) │
│   └─ 4. Attribute Roll Scoring  │
└────────────────┬────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────────────────┐
│ data-lake/01_Bronze/division_2/                        │
│ {YYYYMMDD}_local_inventory_snapshot.csv                │
└────────────────────────────────────────────────────────┘
```

---

## Detailed Phases & Milestones

### Phase 1: Lightweight Hotkey Capture Tool
* **Goal**: A background Python script that captures the gear inspection card whenever a designated hotkey is pressed while browsing inventory or the stash.
* **Key Components**:
  * Global hotkey listener (`keyboard` or `pynput`).
  * Screen capture via `mss` or `Pillow.ImageGrab` constrained to the gear card bounding box `(x1, y1, x2, y2)`.
  * Audio confirmation via `winsound.Beep` for instant feedback without needing to alt-tab.
  * Auto-saving images to `td2/captures/raw/{YYYYMMDD_HHMMSS_ffffff}.png`.
* **Deliverable**: `td2/capture_gear_card.py`

### Phase 2: ROI Calibration & Image Preprocessing
* **Goal**: Define exact crop regions for different screen resolutions (1080p, 1440p, 4K) and clean up contrast for the OCR engine.
* **Gear Card Sub-Regions**:
  1. **Header Zone**: Item Name, Item Category/Slot (Mask, Chest, Assault Rifle, etc.), Rarity color (Exotic, High-End, Gear Set).
  2. **Brand / Gear Set Zone**: Brand Name (e.g., *Grupo Sombra S.A.*, *Ceska Vyroba s.r.o.*) or Gear Set Name (e.g., *Striker's Battlegear*).
  3. **Core Attribute Zone**: Value + Stat Name (e.g., `+15.0% Weapon Damage`, `+170,000 Armor`, `+1 Skill Tier`).
  4. **Minor Attribute Zone**: Value + Stat Name (e.g., `+6.0% Critical Hit Chance`, `+12.0% Critical Hit Damage`).
  5. **Talent Zone**: Talent Name (e.g., *Obliterate*, *In Sync*) — on Chests, Backpacks, and Weapons.
  6. **Mod Slot Zone**: Offensive/Defensive/Utility gear mod or weapon attachment slots.
* **Image Processing**:
  * Grayscale conversion, contrast stretching, and binary thresholding using OpenCV (`cv2`) or Pillow to isolate text from transparent UI backgrounds.
* **Deliverable**: `td2/calibrate_roi.py`

### Phase 3: OCR Text Extraction Engine
* **Goal**: Extract raw alphanumeric strings and roll indicators from cropped sub-regions.
* **Tooling**:
  * Local OCR engine: `easyocr` or `pytesseract` (installed into `.venv` via `uv pip`).
* **Extraction Logic**:
  * Regex pattern matching for values, decimals, and percentages: `(\+?\d+[\.,]?\d*)\s*(%?)`.
  * Text extraction for attribute labels, brands, and talent titles.
  * Roll bar detection (visual or numeric) to identify max/god-roll stats.
* **Deliverable**: Core extraction functions in `td2/parse_inventory_images.py`.

### Phase 4: Catalog Reconciliation & Fuzzy Matching
* **Goal**: Clean OCR noise by validating against known items from the existing project catalog.
* **Integration with Existing Codebase**:
  * Utilizes `td2/loader.py` and `Catalog`:
    * `catalog.weapons` & `catalog.gear`
    * `catalog.weapon_talents` & `catalog.gear_talents`
    * `catalog.attributes` (contains max roll values from `ext_attributes_all.csv`)
  * String fuzzy matching using `rapidfuzz`:
    * Corrects minor OCR misreadings (e.g., `"Stnker's Battlegear"` -> `"Striker's Battlegear"`).
* **Roll Quality Calculation**:
  * Computes attribute roll percentage against maximum theoretical roll:
    $$\text{Roll Quality \%} = \frac{\text{Parsed Value}}{\text{Catalog Max Roll}} \times 100$$
* **Deliverable**: Matching and validation layer in `td2/parse_inventory_images.py`.

### Phase 5: Structured Data Model & Data Lake Storage
* **Goal**: Store the parsed player inventory according to the project's data standards.
* **Compliance Rules (agent/ENVIRONMENT.md)**:
  * Native Python / standard library (`csv.DictReader`, `csv.DictWriter`, `dataclasses`).
  * **No pandas** in reusable code.
  * Standard file docstring headers (`Description`, `Source Data`, `Outputs`).
  * Bronze Layer storage path: `data-lake/01_Bronze/division_2/{YYYYMMDD}_local_inventory_snapshot.csv`.
* **Output Schema**:
  * `timestamp`
  * `item_name`
  * `item_slot`
  * `item_category`
  * `rarity`
  * `brand_or_set`
  * `core_attribute_1`, `core_value_1`, `core_quality_1`
  * `minor_attribute_1`, `minor_value_1`, `minor_quality_1`
  * `minor_attribute_2`, `minor_value_2`, `minor_quality_2`
  * `talent`
  * `is_god_roll`
  * `source_image_filename`
* **Deliverable**: Updated `td2/models.py` (`InventoryItem` dataclass) and CSV writer.

---

## File Structure

```
td2/
├── captures/
│   ├── raw/                       # Raw screenshots from the hotkey tool
│   └── processed/                 # Archived images after batch parsing
├── INVENTORY_SCANNER_PLAN.md      # This project plan
├── capture_gear_card.py           # Phase 1: Background hotkey capture listener
├── calibrate_roi.py               # Phase 2: ROI coordinate calibration helper
├── parse_inventory_images.py      # Phase 3 & 4: OCR, catalog matching, and CSV exporter
├── loader.py                      # (Existing) Loads Bronze CSVs into Catalog
├── models.py                      # (Existing) Model definitions (extend with InventoryItem)
└── ...
```

---

## Prerequisites & Dependencies

To install required libraries in the project virtual environment, run via the `uv` CLI:
```powershell
C:\Users\peter\.local\bin\uv.exe pip install --python c:\Users\peter\Desktop\vscode\main\.venv\Scripts\python.exe keyboard mss pillow rapidfuzz easyocr opencv-python
```

---

## Resumption Checklist

When resuming this task:
1. [ ] Install dependencies into `.venv` using the command above.
2. [ ] Launch *The Division 2* and capture 2–3 sample screenshots of the inventory/stash inspection card.
3. [ ] Run/create `calibrate_roi.py` to identify pixel coordinates for the card on the user's primary monitor.
4. [ ] Build `capture_gear_card.py` to streamline multi-item screenshot collection.
5. [ ] Build `parse_inventory_images.py` to run OCR and output the snapshot CSV into `data-lake/01_Bronze/division_2/`.
