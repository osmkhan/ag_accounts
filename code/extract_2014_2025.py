# pip install dbfread
from pathlib import Path
from dbfread import DBF
import csv, re, sys

# -------- config --------
ROOT = Path("/Users/osmankhan/Desktop/agro_accounts/")  # parent holding dal_1314 ... dal_2526
OUT_DIR = ROOT / "ag_data_2014_2025"
OUT_DIR.mkdir(exist_ok=True)
OUT_ACLIST = OUT_DIR / "ACLIST_1425.csv"
OUT_JOURNAL = OUT_DIR / "JOURNAL_1425.csv"

CANDIDATE_ENCS = ["cp1256","cp864","cp437","cp850","cp1252","latin1"]

# -------- helpers --------
def year_from_folder(name:str):
    m = re.search(r"dal_(\d{4})", name.lower())
    if not m: return None
    yy = int(m.group(1)[:2])
    return 2000 + yy  # 1314->2013, 1415->2014 etc.

def open_dbf_robust(path:Path):
    last = None
    for enc in CANDIDATE_ENCS:
        try:
            t = DBF(str(path), encoding=enc, load=True,
                    ignore_missing_memofile=True, char_decode_errors="replace")
            return t, enc
        except Exception as e:
            last = e
    raise last

def find_case_insensitive(folder:Path, basename_no_ext:str):
    base = basename_no_ext.lower()
    for p in folder.iterdir():
        if p.is_file() and p.stem.lower() == base and p.suffix.lower() == ".dbf":
            return p
    return None

def folders_to_process():
    fs = [p for p in ROOT.iterdir() if p.is_dir() and p.name.lower().startswith("dal_")]
    fs.sort()
    print(f"Found {len(fs)} dal folders.")
    for f in fs:
        y = year_from_folder(f.name)
        print(f"  {f.name}  -> start_year={y}")
    return fs

# -------- PASS 1: collect schemas --------
def collect_columns(fs, base_name):
    cols = set()
    present = 0
    for folder in fs:
        y = year_from_folder(folder.name)
        if y is None or y < 2014:
            continue
        dbf = find_case_insensitive(folder, base_name)
        if not dbf: 
            continue
        try:
            tbl, enc = open_dbf_robust(dbf)
            cols.update([c.strip().upper() for c in tbl.field_names])
            present += 1
        except Exception as e:
            print(f"⚠️  {dbf} skipped: {e}")
    if present == 0:
        print(f"‼️  No {base_name}.dbf found for 2014+")
    cols.update(["_SOURCE_FOLDER","_SOURCE_FILE","_START_YEAR"])
    return sorted(cols)

# -------- PASS 2: stream rows --------
def write_master(fs, base_name, out_path, columns):
    if out_path.exists():
        out_path.unlink()
    wrote_any = False
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(columns)
        for folder in fs:
            y = year_from_folder(folder.name)
            if y is None or y < 2014:
                continue
            dbf = find_case_insensitive(folder, base_name)
            if not dbf:
                continue
            try:
                tbl, enc = open_dbf_robust(dbf)
                print(f"Processing {dbf} (enc={enc})")
                base = dbf.with_suffix("")
                has_memo = any(f.type == "M" for f in tbl.fields)
                has_fpt = base.with_suffix(".FPT").exists() or base.with_suffix(".fpt").exists()
                if has_memo and not has_fpt:
                    print(f"   WARNING: missing memo file for {dbf.name}")
                for rec in tbl:
                    row = {}
                    for k in tbl.field_names:
                        key = k.strip().upper()
                        v = rec.get(k)
                        if hasattr(v, "isoformat"):
                            v = v.isoformat()
                        elif isinstance(v, bytes):
                            v = v.decode(enc, errors="replace")
                        row[key] = v
                    row["_SOURCE_FOLDER"] = folder.name
                    row["_SOURCE_FILE"]   = dbf.name
                    row["_START_YEAR"]    = y
                    w.writerow([row.get(c, None) for c in columns])
                    wrote_any = True
            except Exception as e:
                print(f"⚠️  {dbf} skipped: {e}")
    if wrote_any:
        print(f"✅ Wrote {out_path}")
    else:
        print(f"‼️  Wrote header only (no rows) to {out_path}")

# -------- main --------
def main():
    fs = folders_to_process()
    aclist_cols  = collect_columns(fs, "ACLIST")
    journal_cols = collect_columns(fs, "JOURNAL")
    print(f"\nACLIST columns ({len(aclist_cols)})")
    print(f"JOURNAL columns ({len(journal_cols)})\n")
    write_master(fs, "ACLIST",  OUT_ACLIST,  aclist_cols)
    write_master(fs, "JOURNAL", OUT_JOURNAL, journal_cols)
    print("\nDone.\nOutputs:")
    print(f"  {OUT_ACLIST}")
    print(f"  {OUT_JOURNAL}")

if __name__ == "__main__":
    sys.exit(main())
