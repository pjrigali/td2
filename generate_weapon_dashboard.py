"""
Description:
    Generates a self-contained HTML dashboard with two views:
    (1) Weapon Comparison — ranks all weapons across 6 classes by DPS metrics,
        with class/rarity filters and sortable columns.
    (2) Gear Optimizer — shows ranked brand/gear-set combinations for each
        analyzed weapon loadout, filterable by slot-fill pattern.
    Reads Silver layer CSVs and embeds all data directly into the HTML so it
    can be opened in any browser without a server.

Source Data:
    data-lake/02_Silver/division_2/*_local_weapons_{class}_ranked.csv
    data-lake/02_Silver/division_2/*_local_brands_*_optimized.csv

Outputs:
    td2/dashboard_weapons.html  — open directly in a browser
"""

from __future__ import annotations
import csv
import glob
import json
import os
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SILVER_DIR = os.path.normpath(
    os.path.join(SCRIPT_DIR, "..", "data-lake", "02_Silver", "division_2")
)
OUT_PATH = os.path.join(SCRIPT_DIR, "dashboard_weapons.html")

CLASSES = ["assault_rifles", "smgs", "rifles", "shotguns", "mmrs", "lmgs", "pistols"]
CLASS_LABELS = {
    "assault_rifles": "Assault Rifles",
    "smgs":           "SMGs",
    "rifles":         "Rifles",
    "shotguns":       "Shotguns",
    "mmrs":           "Snipers (MMR)",
    "lmgs":           "LMGs",
    "pistols":        "Pistols",
}

LOADOUT_LABELS = {
    "assault_rifles+smgs": "Assault Rifles + SMGs",
    "rifles+smgs":         "Rifles + SMGs",
    "rifles+shotguns":     "Rifles + Shotguns",
    "mmrs+shotguns":       "MMRs + Shotguns",
}

PATTERN_ORDER = ["3-3", "3-2-1", "2-2-2", "2-2-1-1", "GS2+2+2", "GS2+3+1", "GS3+3", "GS3+2+1"]


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def _latest(pattern: str) -> str | None:
    matches = glob.glob(os.path.join(SILVER_DIR, pattern))
    return sorted(matches, reverse=True)[0] if matches else None


def load_class(weapon_class: str) -> list[dict]:
    path = _latest(f"*_local_weapons_{weapon_class}_ranked.csv")
    if not path:
        print(f"  WARNING: no ranked CSV for {weapon_class} — skipping")
        return []
    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    result = []
    for row in rows:
        result.append({
            "rank":    int(row["rank"]),
            "cls":     weapon_class,
            "name":    row["name"],
            "flag":    row["flag"].strip("[]") if row["flag"] in ("[X]", "[N]") else row["flag"],
            "family":  row["family"],
            "dmg":     float(row["base_damage"]),
            "rpm":     int(row["base_rpm"]),
            "mag":     int(row["base_mag_size"]),
            "reload":  float(row["base_reload_time"]),
            "range":   int(row["optimal_range"]),
            "hsd":     float(row["hsd"]),
            "raw":     int(float(row["raw_dps"])),
            "sus":     int(float(row["sustained_dps"])),
            "hsd_dps": int(float(row["headshot_dps"])),
        })
    return result


def load_optimizer_data() -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = {}
    paths = glob.glob(os.path.join(SILVER_DIR, "*_local_brands_*_optimized.csv"))
    for path in sorted(paths, reverse=True):
        with open(path, encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        for row in rows:
            loadout = row["weapon_types"]
            if loadout not in result:
                result[loadout] = []
            result[loadout].append({
                "rank":    int(row["rank"]),
                "pattern": row["pattern"],
                "score":   float(row["score"]),
                "combo":   row["combo"],
            })
    return result


# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------

HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TD2 Dashboard</title>
<style>
  :root {{
    --bg: #1a1a1f;
    --surface: #22222a;
    --surface-2: #2a2a34;
    --border: #33333d;
    --border-strong: #44444f;
    --text: #e8e8f0;
    --text-secondary: #9999aa;
    --text-muted: #66667a;
    --accent: #7b8cde;
    --gold: #f5c842;
    --green: #6ec87a;
    --flag-x-bg: #3d1a14; --flag-x: #f08060;
    --flag-n-bg: #142a3d; --flag-n: #60a8f0;
    --flag-b: #555566;
    --gs-bg: #2d2414; --gs-text: #e8b84b;
    --brand-bg: #1e2535; --brand-text: #8fb8e8;
    --row-top: rgba(245,200,66,0.07);
    --row-hover: rgba(255,255,255,0.04);
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: var(--bg); color: var(--text); font-family: system-ui, -apple-system, sans-serif; font-size: 13px; padding: 1.5rem; }}
  h1 {{ font-size: 18px; font-weight: 600; margin-bottom: .25rem; }}
  .subtitle {{ font-size: 12px; color: var(--text-muted); margin-bottom: 1.25rem; }}

  /* Tab nav */
  .tab-nav {{ display: flex; gap: 4px; margin-bottom: 1.25rem; border-bottom: 1px solid var(--border); padding-bottom: 0; }}
  .tab-btn {{
    background: none; border: none; border-bottom: 2px solid transparent;
    color: var(--text-secondary); padding: 6px 14px; cursor: pointer;
    font-size: 13px; font-weight: 500; margin-bottom: -1px; border-radius: 0; transition: all .15s;
  }}
  .tab-btn:hover {{ color: var(--text); }}
  .tab-btn.act {{ color: var(--accent); border-bottom-color: var(--accent); }}

  .tab-pane {{ display: none; }}
  .tab-pane.act {{ display: block; }}

  /* Controls */
  .controls {{ display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 1.25rem; align-items: center; }}
  .ctrl-group {{ display: flex; gap: 4px; align-items: center; }}
  .ctrl-label {{ font-size: 11px; color: var(--text-secondary); margin-right: 4px; }}
  button {{
    background: var(--surface-2); border: 1px solid var(--border); color: var(--text-secondary);
    padding: 4px 12px; border-radius: 4px; cursor: pointer; font-size: 12px; transition: all .15s;
  }}
  button:hover {{ color: var(--text); border-color: var(--border-strong); }}
  button.act {{ border-color: var(--accent); color: var(--accent); }}

  /* Stats */
  .stats-row {{ display: flex; gap: 16px; margin-bottom: 1rem; flex-wrap: wrap; }}
  .stat-card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 6px; padding: .6rem 1rem; min-width: 140px; }}
  .stat-label {{ font-size: 11px; color: var(--text-muted); margin-bottom: 2px; }}
  .stat-value {{ font-size: 15px; font-weight: 600; }}
  .stat-sub {{ font-size: 11px; color: var(--text-secondary); }}

  /* Table */
  .table-wrap {{ overflow-x: auto; border-radius: 6px; border: 1px solid var(--border); }}
  table {{ width: 100%; border-collapse: collapse; }}
  th {{
    padding: 7px 10px; font-weight: 500; font-size: 11px; color: var(--text-secondary);
    border-bottom: 1px solid var(--border-strong); text-align: left; white-space: nowrap;
    background: var(--surface); cursor: pointer; user-select: none;
  }}
  th:hover {{ color: var(--text); }}
  th.sorted {{ color: var(--accent); }}
  th.r, td.r {{ text-align: right; }}
  td {{ padding: 5px 10px; border-bottom: 1px solid var(--border); white-space: nowrap; vertical-align: middle; }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover td {{ background: var(--row-hover); }}
  tr.top td {{ background: var(--row-top); }}

  /* Weapon flags */
  .flag-x {{ display: inline-block; padding: 1px 5px; border-radius: 3px; font-size: 10px; font-weight: 700; background: var(--flag-x-bg); color: var(--flag-x); }}
  .flag-n {{ display: inline-block; padding: 1px 5px; border-radius: 3px; font-size: 10px; font-weight: 700; background: var(--flag-n-bg); color: var(--flag-n); }}
  .flag-b {{ font-size: 11px; color: var(--flag-b); }}
  .rank-1 {{ font-weight: 700; color: var(--gold); }}

  /* Gear optimizer brands */
  .combo-wrap {{ display: flex; flex-wrap: wrap; gap: 5px; white-space: normal; }}
  .brand-pill {{
    display: inline-flex; align-items: center; gap: 4px;
    background: var(--brand-bg); color: var(--brand-text);
    padding: 2px 7px; border-radius: 3px; font-size: 11px; white-space: nowrap;
  }}
  .brand-pill.gs {{ background: var(--gs-bg); color: var(--gs-text); }}
  .brand-pill .pcs {{ font-weight: 700; font-size: 12px; }}
  .pat-badge {{
    display: inline-block; padding: 1px 6px; border-radius: 3px; font-size: 10px; font-weight: 600;
    background: var(--surface-2); color: var(--text-secondary); border: 1px solid var(--border); white-space: nowrap;
  }}
  .pat-badge.gs-pat {{ color: var(--gs-text); border-color: #5a4010; background: #2a2010; }}

  /* Bar */
  .bar-cell {{ display: flex; align-items: center; gap: 6px; }}
  .bar {{ height: 6px; border-radius: 3px; background: var(--accent); opacity: .7; min-width: 2px; }}
  .bar.green {{ background: var(--green); }}

  .hidden {{ display: none; }}
  footer {{ margin-top: 1.5rem; font-size: 11px; color: var(--text-muted); }}
</style>
</head>
<body>
<h1>TD2 Dashboard</h1>
<p class="subtitle">Generated {generated}. Data from Silver layer. Talent rolls excluded from scoring.</p>

<div class="tab-nav">
  <button class="tab-btn act" onclick="switchTab('weapons')">Weapons</button>
  <button class="tab-btn" onclick="switchTab('gear')">Gear Optimizer</button>
</div>

<!-- ===== WEAPONS TAB ===== -->
<div id="tab-weapons" class="tab-pane act">
  <div class="controls">
    <div class="ctrl-group">
      <span class="ctrl-label">Class:</span>
      <button id="cls-all" onclick="toggleCls('all')">All</button>
      {class_buttons}
    </div>
  </div>
  <div class="controls" style="margin-top:-.5rem">
    <div class="ctrl-group">
      <span class="ctrl-label">Show:</span>
      <button id="tog-base" class="act" onclick="toggleFlag('base')">Normal</button>
      <button id="tog-N" class="act" onclick="toggleFlag('N')">Named</button>
      <button id="tog-X" class="act" onclick="toggleFlag('X')">Exotic</button>
    </div>
    <div class="ctrl-group">
      <span class="ctrl-label">Sort:</span>
      <button id="sort-hsd_dps" class="act" onclick="setSort('hsd_dps')">HSD DPS</button>
      <button id="sort-sus" onclick="setSort('sus')">Sus DPS</button>
      <button id="sort-raw" onclick="setSort('raw')">Raw DPS</button>
    </div>
  </div>
  <div class="stats-row" id="w-stats-row"></div>
  <div class="table-wrap">
    <table>
      <thead><tr id="w-thead-row"></tr></thead>
      <tbody id="w-tbody"></tbody>
    </table>
  </div>
</div>

<!-- ===== GEAR OPTIMIZER TAB ===== -->
<div id="tab-gear" class="tab-pane">
  <div class="controls">
    <div class="ctrl-group">
      <span class="ctrl-label">Loadout:</span>
      {loadout_buttons}
    </div>
  </div>
  <div class="controls" style="margin-top:-.5rem">
    <div class="ctrl-group">
      <span class="ctrl-label">Pattern:</span>
      <button id="pat-all" class="act" onclick="setPat('all')">All</button>
      {pattern_buttons}
    </div>
  </div>
  <div class="stats-row" id="g-stats-row"></div>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th class="r" onclick="gDoSort('g_rank')">#</th>
          <th onclick="gDoSort('pattern')">Pattern</th>
          <th class="r" onclick="gDoSort('score')">Score</th>
          <th>Combination</th>
        </tr>
      </thead>
      <tbody id="g-tbody"></tbody>
    </table>
  </div>
</div>

<footer>TD2 Dashboard &mdash; regenerate with <code>python td2/generate_weapon_dashboard.py</code></footer>

<script>
// ── Data ──────────────────────────────────────────────────────────────────
const W_DATA = {w_data_json};
const G_DATA = {g_data_json};
const CLS_LABELS = {cls_labels_json};
const ALL_CLASSES = {all_classes_json};
const LOADOUT_LABELS = {loadout_labels_json};
const PATTERN_ORDER = {pattern_order_json};

// ── Tab switch ────────────────────────────────────────────────────────────
function switchTab(t) {{
  ["weapons","gear"].forEach(id => {{
    document.getElementById("tab-"+id).classList.toggle("act", id===t);
    document.querySelectorAll(".tab-btn").forEach((b,i) => b.classList.toggle("act", ["weapons","gear"][i]===t));
  }});
}}

// ═══════════════════════════════════════════════════════════════════════════
// WEAPONS TAB
// ═══════════════════════════════════════════════════════════════════════════
let selectedCls = new Set(["assault_rifles"]);
let wSortKey="hsd_dps", wSortDir=1;
let flags={{base:true, N:true, X:true}};

const W_COLS = [
  {{key:"rank",   label:"#",       r:true,  fmt:(v,w)=>v===1?'<span class="rank-1">1</span>':v}},
  {{key:"flag",   label:"",        r:false, fmt:(v,w)=>v==="X"?'<span class="flag-x">X</span>':v==="N"?'<span class="flag-n">N</span>':'<span class="flag-b">·</span>'}},
  {{key:"name",   label:"Name",    r:false, fmt:(v,w)=>v}},
  {{key:"family", label:"Family",  r:false, fmt:(v,w)=>`<span style="color:var(--text-secondary)">${{v}}</span>`}},
  {{key:"dmg",    label:"Damage",  r:true,  fmt:(v,w)=>v.toLocaleString()}},
  {{key:"rpm",    label:"RPM",     r:true,  fmt:(v,w)=>v}},
  {{key:"mag",    label:"Mag",     r:true,  fmt:(v,w)=>v}},
  {{key:"reload", label:"Reload",  r:true,  fmt:(v,w)=>v.toFixed(2)+"s"}},
  {{key:"range",  label:"Range",   r:true,  fmt:(v,w)=>v}},
  {{key:"hsd",    label:"HSD%",    r:true,  fmt:(v,w)=>v+"%"}},
  {{key:"raw",    label:"Raw DPS", r:true,  fmt:(v,w)=>v.toLocaleString()}},
  {{key:"sus",    label:"Sus DPS", r:true,  fmt:(v,w)=>v.toLocaleString()}},
  {{key:"hsd_dps",label:"HSD DPS", r:true,  fmt:(v,w)=>{{
    const max=wMax("hsd_dps");
    const pct=max?Math.round(v/max*100):0;
    return `<div class="bar-cell"><span>${{v.toLocaleString()}}</span><div class="bar" style="width:${{Math.max(pct*.6,2)}}px"></div></div>`;
  }}}},
];

function wAllRows(){{ let o=[]; for(const c of selectedCls) o=o.concat(W_DATA[c]||[]); return o; }}
function wMax(k){{ const r=wAllRows(); return r.length?Math.max(...r.map(x=>x[k])):1; }}
function wTotal(){{ let n=0; for(const c of selectedCls) n+=(W_DATA[c]||[]).length; return n; }}
function wFiltered(){{ return wAllRows().filter(r=>flags[r.flag]); }}
function wSorted(){{ return wFiltered().slice().sort((a,b)=>wSortDir*(b[wSortKey]-a[wSortKey])); }}
function wMulti(){{ return selectedCls.size!==1; }}

function wRender() {{
  const rows=wSorted(); const multi=wMulti();
  const sr=document.getElementById("w-stats-row");
  if(rows.length){{
    const top=rows[0];
    const lbl=multi?CLS_LABELS[top.cls]:(CLS_LABELS[[...selectedCls][0]]||"");
    sr.innerHTML=`
      <div class="stat-card"><div class="stat-label">Top weapon</div><div class="stat-value">${{top.name}}</div><div class="stat-sub">${{top.flag==="X"?"Exotic":top.flag==="N"?"Named":"Base"}}${{multi?" · "+lbl:""}}</div></div>
      <div class="stat-card"><div class="stat-label">HSD DPS (top)</div><div class="stat-value">${{top.hsd_dps.toLocaleString()}}</div><div class="stat-sub">sustained × HSD</div></div>
      <div class="stat-card"><div class="stat-label">Showing</div><div class="stat-value">${{rows.length}}</div><div class="stat-sub">of ${{wTotal()}} weapons</div></div>`;
  }} else sr.innerHTML="";

  const cols=multi?[W_COLS[0],{{key:"cls",label:"Class",r:false,fmt:(v)=>`<span style="color:var(--text-secondary);font-size:11px">${{CLS_LABELS[v]||v}}</span>`}},...W_COLS.slice(1)]:W_COLS;
  const hr=document.getElementById("w-thead-row");
  hr.innerHTML=cols.map(c=>{{
    const isSorted=c.key===wSortKey?"sorted":"";
    const arrow=c.key===wSortKey?(wSortDir===1?"↓":"↑"):"";
    return `<th class="${{c.r?"r":""}} ${{isSorted}}" onclick="wDoSort('${{c.key}}')">${{c.label}}${{arrow?` ${{arrow}}`:""}}</th>`;
  }}).join("");
  const body=document.getElementById("w-tbody");
  body.innerHTML=rows.map((w,i)=>{{
    const topCls=i===0?"top":"";
    return `<tr class="${{topCls}}">${{cols.map(c=>`<td class="${{c.r?"r":""}}">${{c.fmt(w[c.key],w)}}</td>`).join("")}}</tr>`;
  }}).join("");
}}

function toggleCls(c){{
  if(c==="all"){{
    const allOn=ALL_CLASSES.every(x=>selectedCls.has(x));
    selectedCls=allOn?new Set(["assault_rifles"]):new Set(ALL_CLASSES);
  }} else {{
    if(selectedCls.has(c)&&selectedCls.size===1) return;
    if(selectedCls.has(c)) selectedCls.delete(c); else selectedCls.add(c);
  }}
  syncClsButtons(); wRender();
}}
function syncClsButtons(){{
  const allOn=ALL_CLASSES.every(x=>selectedCls.has(x));
  document.getElementById("cls-all").classList.toggle("act",allOn);
  ALL_CLASSES.forEach(c=>{{ const el=document.getElementById("cls-"+c); if(el) el.classList.toggle("act",selectedCls.has(c)); }});
}}
function toggleFlag(f){{ flags[f]=!flags[f]; document.getElementById("tog-"+f).classList.toggle("act",flags[f]); wRender(); }}
function setSort(k){{
  if(wSortKey===k) wSortDir*=-1; else{{wSortKey=k;wSortDir=1;}}
  ["hsd_dps","sus","raw"].forEach(x=>document.getElementById("sort-"+x).classList.toggle("act",x===k));
  wRender();
}}
function wDoSort(k){{ if(wSortKey===k) wSortDir*=-1; else{{wSortKey=k;wSortDir=1;}} wRender(); }}

// ═══════════════════════════════════════════════════════════════════════════
// GEAR OPTIMIZER TAB
// ═══════════════════════════════════════════════════════════════════════════
const LOADOUT_KEYS = Object.keys(G_DATA);
let selectedLoadout = LOADOUT_KEYS[0] || "";
let selectedPat = "all";
let gSortKey = "score", gSortDir = 1;

function gRows() {{
  const rows = G_DATA[selectedLoadout] || [];
  const filtered = selectedPat === "all" ? rows : rows.filter(r => r.pattern === selectedPat);
  // assign global rank by score within current filter
  const sorted = filtered.slice().sort((a,b)=>b.score-a.score);
  return sorted.map((r,i)=>Object.assign({{g_rank:i+1}},r));
}}

function gMaxScore(){{ const r=gRows(); return r.length?Math.max(...r.map(x=>x.score)):1; }}

function renderCombo(combo){{
  return '<div class="combo-wrap">'+combo.split(' | ').map(part=>{{
    const isGS=part.startsWith('[GS] ');
    const clean=part.replace('[GS] ','');
    const match=clean.match(/^(.*?)[\\s]+×([\\d]+)$/);
    const name=match?match[1]:clean;
    const pcs=match?match[2]:'';
    const cls='brand-pill'+(isGS?' gs':'');
    return `<span class="${{cls}}">${{isGS?'<span style="font-size:9px;opacity:.7">GS</span> ':''}}${{name}}${{pcs?` <span class="pcs">×${{pcs}}</span>`:''}}</span>`;
  }}).join('')+'</div>';
}}

function gRender(){{
  const rows=gRows(); const maxS=gMaxScore();
  const sr=document.getElementById("g-stats-row");
  if(rows.length){{
    const top=rows[0];
    const patLabel=selectedPat==="all"?"All patterns":selectedPat;
    sr.innerHTML=`
      <div class="stat-card"><div class="stat-label">Top combination</div><div class="stat-value" style="font-size:12px;line-height:1.4">${{top.combo.replace(/\\[GS\\][\\s]*/g,'').replace(/ [|] /g,' · ')}}</div><div class="stat-sub">${{top.pattern}} · score ${{top.score}}</div></div>
      <div class="stat-card"><div class="stat-label">Pattern</div><div class="stat-value">${{patLabel}}</div><div class="stat-sub">${{rows.length}} combination${{rows.length!==1?"s":""}}</div></div>
      <div class="stat-card"><div class="stat-label">Top score</div><div class="stat-value">${{top.score.toLocaleString()}}</div><div class="stat-sub">weighted bonus total</div></div>`;
  }} else sr.innerHTML="";

  const body=document.getElementById("g-tbody");
  body.innerHTML=rows.map((r,i)=>{{
    const topCls=i===0?"top":"";
    const isGsPat=r.pattern.startsWith("GS");
    const patBadge=`<span class="pat-badge${{isGsPat?" gs-pat":""}}">${{r.pattern}}</span>`;
    const pct=maxS?Math.round(r.score/maxS*100):0;
    const bar=`<div class="bar-cell"><span>${{r.score.toLocaleString()}}</span><div class="bar green" style="width:${{Math.max(pct*.6,2)}}px"></div></div>`;
    return `<tr class="${{topCls}}">
      <td class="r">${{r.g_rank===1?'<span class="rank-1">1</span>':r.g_rank}}</td>
      <td>${{patBadge}}</td>
      <td class="r">${{bar}}</td>
      <td>${{renderCombo(r.combo)}}</td>
    </tr>`;
  }}).join("");
}}

function setLoadout(l){{
  selectedLoadout=l; selectedPat="all";
  LOADOUT_KEYS.forEach(k=>{{ const el=document.getElementById("load-"+k); if(el) el.classList.toggle("act",k===l); }});
  syncPatButtons(); gRender();
}}
function setPat(p){{
  selectedPat=p; syncPatButtons(); gRender();
}}
function syncPatButtons(){{
  document.getElementById("pat-all").classList.toggle("act",selectedPat==="all");
  PATTERN_ORDER.forEach(p=>{{ const el=document.getElementById("pat-"+p.replace(/[+]/g,"_")); if(el) el.classList.toggle("act",selectedPat===p); }});
}}
function gDoSort(k){{
  if(gSortKey===k) gSortDir*=-1; else{{gSortKey=k;gSortDir=1;}}
  gRender();
}}

// ── Init ─────────────────────────────────────────────────────────────────
wRender();
if(selectedLoadout) gRender();
</script>
</body>
</html>
"""


def main() -> None:
    print("Loading weapon data...")
    w_data: dict[str, list] = {}
    for wc in CLASSES:
        rows = load_class(wc)
        w_data[wc] = rows
        print(f"  {CLASS_LABELS[wc]}: {len(rows)} weapons")

    print("\nLoading gear optimizer data...")
    g_data = load_optimizer_data()
    for loadout, rows in g_data.items():
        label = LOADOUT_LABELS.get(loadout, loadout)
        patterns = sorted({r["pattern"] for r in rows})
        print(f"  {label}: {len(rows)} rows, patterns: {patterns}")

    # --- Build buttons ---
    class_buttons = " ".join(
        f'<button id="cls-{wc}" class="{"act" if wc == "assault_rifles" else ""}" onclick="toggleCls(\'{wc}\')">{label}</button>'
        for wc, label in CLASS_LABELS.items()
    )

    ordered_loadouts = [k for k in LOADOUT_LABELS if k in g_data]
    ordered_loadouts += [k for k in g_data if k not in LOADOUT_LABELS]
    first_loadout = ordered_loadouts[0] if ordered_loadouts else ""
    loadout_buttons = " ".join(
        f'<button id="load-{lk}" class="{"act" if lk == first_loadout else ""}" onclick="setLoadout(\'{lk}\')">{LOADOUT_LABELS.get(lk, lk)}</button>'
        for lk in ordered_loadouts
    )

    all_patterns = []
    for p in PATTERN_ORDER:
        if any(r["pattern"] == p for rows in g_data.values() for r in rows):
            all_patterns.append(p)

    pattern_buttons = " ".join(
        f'<button id="pat-{p.replace("+", "_")}" onclick="setPat(\'{p}\')">{p}</button>'
        for p in all_patterns
    )

    html = HTML_TEMPLATE.format(
        generated=datetime.now().strftime("%Y-%m-%d %H:%M"),
        class_buttons=class_buttons,
        loadout_buttons=loadout_buttons,
        pattern_buttons=pattern_buttons,
        w_data_json=json.dumps(w_data, separators=(",", ":")),
        g_data_json=json.dumps(g_data, separators=(",", ":")),
        cls_labels_json=json.dumps(CLASS_LABELS, separators=(",", ":")),
        all_classes_json=json.dumps(CLASSES, separators=(",", ":")),
        loadout_labels_json=json.dumps(LOADOUT_LABELS, separators=(",", ":")),
        pattern_order_json=json.dumps(PATTERN_ORDER, separators=(",", ":")),
    )

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    total_w = sum(len(v) for v in w_data.values())
    total_g = sum(len(v) for v in g_data.values())
    print(f"\nDashboard written to: {OUT_PATH}")
    print(f"  {total_w} weapons across {len(CLASSES)} classes")
    print(f"  {total_g} optimizer rows across {len(g_data)} loadouts")
    print("Open in any browser — no server needed.")


if __name__ == "__main__":
    main()
