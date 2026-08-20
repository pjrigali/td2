"""
Description:
    Generates a self-contained HTML dashboard for weapon comparison across
    assault_rifles, smgs, rifles, shotguns, mmrs, and lmgs. Reads the most
    recent ranked CSV for each class from the Silver layer and embeds the data
    directly into the HTML file so it can be opened in any browser without a
    server. Supports multi-class selection and an "All" view.

Source Data:
    data-lake/02_Silver/division_2/*_local_weapons_{class}_ranked.csv

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

CLASSES = ["assault_rifles", "smgs", "rifles", "shotguns", "mmrs", "lmgs"]
CLASS_LABELS = {
    "assault_rifles": "Assault Rifles",
    "smgs":           "SMGs",
    "rifles":         "Rifles",
    "shotguns":       "Shotguns",
    "mmrs":           "Snipers (MMR)",
    "lmgs":           "LMGs",
}


def _latest_ranked(weapon_class: str) -> str | None:
    pattern = os.path.join(SILVER_DIR, f"*_local_weapons_{weapon_class}_ranked.csv")
    matches = glob.glob(pattern)
    if not matches:
        return None
    return sorted(matches, reverse=True)[0]


def load_class(weapon_class: str) -> list[dict]:
    path = _latest_ranked(weapon_class)
    if not path:
        print(f"  WARNING: no ranked CSV found for {weapon_class} — skipping")
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


HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TD2 Weapon Dashboard</title>
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
    --flag-x-bg: #3d1a14; --flag-x: #f08060;
    --flag-n-bg: #142a3d; --flag-n: #60a8f0;
    --flag-b: #555566;
    --row-top: rgba(245,200,66,0.07);
    --row-hover: rgba(255,255,255,0.04);
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: var(--bg); color: var(--text); font-family: system-ui, -apple-system, sans-serif; font-size: 13px; padding: 1.5rem; }}
  h1 {{ font-size: 18px; font-weight: 600; margin-bottom: .25rem; }}
  .subtitle {{ font-size: 12px; color: var(--text-muted); margin-bottom: 1.5rem; }}
  .controls {{ display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 1.25rem; align-items: center; }}
  .ctrl-group {{ display: flex; gap: 4px; align-items: center; }}
  .ctrl-label {{ font-size: 11px; color: var(--text-secondary); margin-right: 4px; }}
  button {{
    background: var(--surface-2); border: 1px solid var(--border); color: var(--text-secondary);
    padding: 4px 12px; border-radius: 4px; cursor: pointer; font-size: 12px; transition: all .15s;
  }}
  button:hover {{ color: var(--text); border-color: var(--border-strong); }}
  button.act {{ border-color: var(--accent); color: var(--accent); }}
  .toggle-group {{ display: flex; gap: 4px; }}
  .stats-row {{ display: flex; gap: 16px; margin-bottom: 1rem; flex-wrap: wrap; }}
  .stat-card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 6px; padding: .6rem 1rem; min-width: 140px; }}
  .stat-label {{ font-size: 11px; color: var(--text-muted); margin-bottom: 2px; }}
  .stat-value {{ font-size: 15px; font-weight: 600; }}
  .stat-sub {{ font-size: 11px; color: var(--text-secondary); }}
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
  .flag-x {{ display: inline-block; padding: 1px 5px; border-radius: 3px; font-size: 10px; font-weight: 700; background: var(--flag-x-bg); color: var(--flag-x); }}
  .flag-n {{ display: inline-block; padding: 1px 5px; border-radius: 3px; font-size: 10px; font-weight: 700; background: var(--flag-n-bg); color: var(--flag-n); }}
  .flag-b {{ font-size: 11px; color: var(--flag-b); }}
  .rank-1 {{ font-weight: 700; color: var(--gold); }}
  .hidden {{ display: none; }}
  .count-badge {{ font-size: 11px; color: var(--text-muted); margin-left: 6px; }}
  footer {{ margin-top: 1.5rem; font-size: 11px; color: var(--text-muted); }}
  .bar-cell {{ display: flex; align-items: center; gap: 6px; }}
  .bar {{ height: 6px; border-radius: 3px; background: var(--accent); opacity: .7; min-width: 2px; }}
</style>
</head>
<body>
<h1>TD2 Weapon Dashboard</h1>
<p class="subtitle">Generated {generated}. Data from Silver layer. Talent rolls excluded from scoring.</p>

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

<div class="stats-row" id="stats-row"></div>

<div class="table-wrap">
<table>
  <thead><tr id="thead-row"></tr></thead>
  <tbody id="tbody"></tbody>
</table>
</div>

<footer>TD2 Weapon Dashboard &mdash; regenerate with <code>python td2/generate_weapon_dashboard.py</code></footer>

<script>
const DATA = {data_json};

const COLS = [
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
    const max=_max("hsd_dps");
    const pct=max?Math.round(v/max*100):0;
    return `<div class="bar-cell"><span>${{v.toLocaleString()}}</span><div class="bar" style="width:${{Math.max(pct*.6,2)}}px"></div></div>`;
  }}}},
];

const CLS_LABELS = {cls_labels_json};
const ALL_CLASSES = {all_classes_json};

let selectedCls = new Set(["assault_rifles"]);
let sortKey="hsd_dps", sortDir=1;
let flags={{base:true, N:true, X:true}};

function allRows(){{
  let out=[];
  for(const c of selectedCls) out=out.concat(DATA[c]||[]);
  return out;
}}

function _max(key){{
  const rows=allRows();
  return rows.length?Math.max(...rows.map(r=>r[key])):1;
}}

function totalCount(){{
  let n=0;
  for(const c of selectedCls) n+=(DATA[c]||[]).length;
  return n;
}}

function filtered(){{
  return allRows().filter(r=>flags[r.flag]);
}}

function sorted(){{
  return filtered().slice().sort((a,b)=>sortDir*(b[sortKey]-a[sortKey]));
}}

function multiMode(){{ return selectedCls.size!==1; }}

function render(){{
  const rows=sorted();
  const multi=multiMode();

  // stats
  const sr=document.getElementById("stats-row");
  if(rows.length){{
    const top=rows[0];
    const clsLabel=multi?CLS_LABELS[top.cls]:(CLS_LABELS[[...selectedCls][0]]||"");
    sr.innerHTML=`
      <div class="stat-card"><div class="stat-label">Top weapon</div><div class="stat-value">${{top.name}}</div><div class="stat-sub">${{top.flag==="X"?"Exotic":top.flag==="N"?"Named":"Base"}}${{multi?" · "+clsLabel:""}}</div></div>
      <div class="stat-card"><div class="stat-label">HSD DPS (top)</div><div class="stat-value">${{top.hsd_dps.toLocaleString()}}</div><div class="stat-sub">sustained × HSD</div></div>
      <div class="stat-card"><div class="stat-label">Showing</div><div class="stat-value">${{rows.length}}</div><div class="stat-sub">of ${{totalCount()}} weapons</div></div>
    `;
  }} else sr.innerHTML="";

  // header — insert Class col when multi-class
  const cols=multi?[COLS[0],{{key:"cls",label:"Class",r:false,fmt:(v)=>`<span style="color:var(--text-secondary);font-size:11px">${{CLS_LABELS[v]||v}}</span>`}},...COLS.slice(1)]:COLS;

  const hr=document.getElementById("thead-row");
  hr.innerHTML=cols.map(c=>{{
    const isSorted=c.key===sortKey?"sorted":"";
    const arrow=c.key===sortKey?(sortDir===1?"↓":"↑"):"";
    return `<th class="${{c.r?"r":""}} ${{isSorted}}" onclick="doSort('${{c.key}}')">${{c.label}}${{arrow?` ${{arrow}}`:""}}</th>`;
  }}).join("");

  // body
  const body=document.getElementById("tbody");
  body.innerHTML=rows.map((w,i)=>{{
    const topCls=i===0?"top":"";
    return `<tr class="${{topCls}}">${{cols.map(c=>`<td class="${{c.r?"r":""}}">${{c.fmt(w[c.key],w)}}</td>`).join("")}}</tr>`;
  }}).join("");
}}

function toggleCls(c){{
  if(c==="all"){{
    const allOn=ALL_CLASSES.every(x=>selectedCls.has(x));
    if(allOn){{ selectedCls=new Set(["assault_rifles"]); }}
    else{{ selectedCls=new Set(ALL_CLASSES); }}
  }} else {{
    if(selectedCls.has(c) && selectedCls.size===1) return; // keep at least one
    if(selectedCls.has(c)) selectedCls.delete(c); else selectedCls.add(c);
  }}
  syncClsButtons();
  render();
}}

function syncClsButtons(){{
  const allOn=ALL_CLASSES.every(x=>selectedCls.has(x));
  document.getElementById("cls-all").classList.toggle("act",allOn);
  ALL_CLASSES.forEach(c=>{{
    const el=document.getElementById("cls-"+c);
    if(el) el.classList.toggle("act",selectedCls.has(c));
  }});
}}

function toggleFlag(f){{
  flags[f]=!flags[f];
  document.getElementById("tog-"+f).classList.toggle("act",flags[f]);
  render();
}}

function setSort(k){{
  if(sortKey===k)sortDir*=-1; else{{sortKey=k;sortDir=1;}}
  ["hsd_dps","sus","raw"].forEach(x=>document.getElementById("sort-"+x).classList.toggle("act",x===k));
  render();
}}

function doSort(k){{
  if(sortKey===k)sortDir*=-1; else{{sortKey=k;sortDir=1;}}
  render();
}}

render();
</script>
</body>
</html>
"""


def main() -> None:
    print("Loading weapon data...")
    all_data: dict[str, list] = {}
    for wc in CLASSES:
        rows = load_class(wc)
        all_data[wc] = rows
        print(f"  {CLASS_LABELS[wc]}: {len(rows)} weapons")

    class_buttons = " ".join(
        f'<button id="cls-{wc}" class="{"act" if wc == "assault_rifles" else ""}" onclick="toggleCls(\'{wc}\')">{label}</button>'
        for wc, label in CLASS_LABELS.items()
    )

    html = HTML_TEMPLATE.format(
        generated=datetime.now().strftime("%Y-%m-%d %H:%M"),
        class_buttons=class_buttons,
        data_json=json.dumps(all_data, separators=(",", ":")),
        cls_labels_json=json.dumps(CLASS_LABELS, separators=(",", ":")),
        all_classes_json=json.dumps(CLASSES, separators=(",", ":")),
    )

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\nDashboard written to: {OUT_PATH}")
    print("Open in any browser — no server needed.")


if __name__ == "__main__":
    main()
