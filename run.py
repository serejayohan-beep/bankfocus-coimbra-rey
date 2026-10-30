"""
Pipeline runner. Reads data locations from config/paths.local.ini (not committed; copy
config/paths.example.ini) or from environment variables, then runs:

  build     raw BankFocus exports  -> derived global panel   (code/build/global_panel.py)
  analysis  derived panel          -> output/ figures, tables (code/analysis/*.py)

Usage
  python run.py build        # writes <derived_dir>/global_panel_*.{csv,dta} + MANIFEST.txt
  python run.py analysis     # writes output/ (figures, .tex tables, aggregate CSVs)
  python run.py all

Bank-level data never goes into this repository: raw exports and derived panels live under
DATA_ROOT (e.g. C:\\Users\\USER\\Desktop\\HG\\Archive\\Data\\Bankfocus).
"""
import configparser
import datetime as dt
import hashlib
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent


def load_paths():
    cfg = configparser.ConfigParser()
    local = REPO / "config" / "paths.local.ini"
    if local.exists():
        cfg.read(local, encoding="utf-8")
    sec = cfg["paths"] if cfg.has_section("paths") else {}

    def get(key, env):
        v = os.environ.get(env) or sec.get(key)
        if not v:
            sys.exit(f"Missing path '{key}': set it in config/paths.local.ini or env var {env}")
        return Path(v).expanduser()

    root = get("data_root", "BANKFOCUS_DATA")
    return {
        "root": root,
        "core": root / get("global_core_raw", "BANKFOCUS_CORE_RAW"),
        "fx": root / get("global_fx_raw", "BANKFOCUS_FX_RAW"),
        "derived": root / get("global_derived", "BANKFOCUS_DERIVED"),
    }


def sha256(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def git_rev():
    try:
        rev = subprocess.check_output(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"], text=True).strip()
        dirty = subprocess.call(["git", "-C", str(REPO), "diff", "--quiet"]) != 0
        return rev + ("-dirty" if dirty else "")
    except Exception:
        return "unknown"


def run(script, *args):
    cmd = [sys.executable, "-I", str(REPO / script), *map(str, args)]
    print(">>", " ".join(cmd))
    subprocess.check_call(cmd)


def build(p):
    p["derived"].mkdir(parents=True, exist_ok=True)
    run("code/build/global_panel.py", p["core"], p["fx"], p["derived"])
    lines = [f"created: {dt.datetime.now().isoformat(timespec='seconds')}",
             f"code: bankfocus-coimbra-rey @ {git_rev()} (code/build/global_panel.py)",
             f"raw core: DATA_ROOT/{p['core'].relative_to(p['root']).as_posix()}",
             f"raw fx: DATA_ROOT/{p['fx'].relative_to(p['root']).as_posix()}",
             f"raw files: {len(list(p['core'].glob('*.xlsx')))} core + {len(list(p['fx'].glob('*.xlsx')))} fx xlsx", ""]
    for f in sorted(p["derived"].glob("global_*")):
        if f.is_file():
            lines.append(f"{f.name}  {f.stat().st_size:>12,d} bytes  sha256={sha256(f)}")
    (p["derived"] / "MANIFEST.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("MANIFEST written:", p["derived"] / "MANIFEST.txt")


def analysis(p):
    panel = p["derived"] / "global_panel_main.csv"
    out = REPO / "output"
    tmp = out / "_tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    run("code/analysis/cr_analysis.py", panel, REPO / "data_public" / "us_ffr_annual.csv", tmp)
    run("code/analysis/region_gfc.py", panel, tmp)
    for f in tmp.iterdir():
        dest = {".png": out / "figures", ".tex": out / "tables", ".csv": out / "region"}.get(f.suffix, out)
        dest.mkdir(exist_ok=True)
        f.replace(dest / f.name)
    tmp.rmdir()


if __name__ == "__main__":
    step = sys.argv[1] if len(sys.argv) > 1 else "all"
    paths = load_paths()
    if step in ("build", "all"):
        build(paths)
    if step in ("analysis", "all"):
        analysis(paths)
