import pandas as pd
from datetime import date
from pathlib import Path

# --- config (UPDATED) ---
ACCOUNT_ID = 263
INCLUDE_CHILDREN = True
ACLIST_PATH = "/Users/osmankhan/Desktop/agro_accounts/ag_data_2014_2025/ACLIST_1425.csv"
JOURNAL_PATH = "/Users/osmankhan/Desktop/agro_accounts/ag_data_2014_2025/JOURNAL_1425.csv"
OUT_DIR = Path("/Users/osmankhan/Desktop/agro_accounts/ag_data_2014_2025/analysis")
OUT_PATH_MONTHLY = OUT_DIR / "telephone_costs.csv"
OUT_PATH_RANGES  = OUT_DIR / "account_date_ranges.csv"
YEARS = 5

OUT_DIR.mkdir(parents=True, exist_ok=True)

# --- load ---
ac = pd.read_csv(ACLIST_PATH, dtype=str, keep_default_na=False)
jn = pd.read_csv(JOURNAL_PATH, dtype=str, keep_default_na=False)

# normalize headers
ac.columns = [c.strip().upper() for c in ac.columns]
jn.columns = [c.strip().upper() for c in jn.columns]

# coerce types (ACLIST)
for col in ["NO","LEVEL","L1","L2","L3","L4","L5"]:
    if col in ac.columns:
        ac[col] = pd.to_numeric(ac[col], errors="coerce")
ac["HEAD"] = ac.get("HEAD", "").astype(str).str.strip()

# journal typed cols
date_col = "TRN_DATE" if "TRN_DATE" in jn.columns else None
if not date_col:
    raise ValueError("Expected TRN_DATE column in JOURNAL.")
keep_cols = [c for c in ["TRN_DATE","AC_NO","DR","CR"] if c in jn.columns]
jn = jn[keep_cols].copy()
jn["TRN_DATE"] = pd.to_datetime(jn["TRN_DATE"], errors="coerce").dt.date
jn["AC_NO"] = pd.to_numeric(jn["AC_NO"], errors="coerce")
jn["DR"] = pd.to_numeric(jn.get("DR", 0), errors="coerce").fillna(0)
jn["CR"] = pd.to_numeric(jn.get("CR", 0), errors="coerce").fillna(0)

# --- account filter (children via L1–L5 path) ---
if INCLUDE_CHILDREN:
    target = ac.loc[ac["NO"] == ACCOUNT_ID]
    if not target.empty and {"LEVEL","L1","L2","L3","L4","L5"}.issubset(ac.columns):
        depth = int(target.iloc[0]["LEVEL"]) if pd.notna(target.iloc[0]["LEVEL"]) else 0
        depth = max(0, min(depth, 5))
        path = [int(target.iloc[0][f"L{i}"]) if pd.notna(target.iloc[0][f"L{i}"]) else None for i in range(1,6)]
        mask_ac = pd.Series(True, index=ac.index)
        for i in range(depth):
            li = f"L{i+1}"
            mask_ac &= (ac[li] == path[i])
        if "LEVEL" in ac.columns:
            mask_ac &= ac["LEVEL"].fillna(0) >= depth
        account_ids = set(ac.loc[mask_ac, "NO"].dropna().astype(int))
    else:
        account_ids = {ACCOUNT_ID}
else:
    account_ids = {ACCOUNT_ID}

# --- journal subset for chosen account(s) ---
lines = jn[jn["AC_NO"].isin(account_ids)].copy()

# --- monthly net over last N years ---
if lines.empty:
    pd.DataFrame(columns=["month","total_cost_pkr"]).to_csv(OUT_PATH_MONTHLY, index=False)
    print("No journal lines for selected account(s). Wrote empty:", OUT_PATH_MONTHLY)
else:
    lines["NET"] = lines["DR"] - lines["CR"]
    today = date.today()
    start = date(today.year - YEARS, today.month, 1)
    lines = lines[(lines["TRN_DATE"] >= start) & (lines["TRN_DATE"] <= today)]
    if lines.empty:
        pd.DataFrame(columns=["month","total_cost_pkr"]).to_csv(OUT_PATH_MONTHLY, index=False)
        print(f"No activity in last {YEARS} years. Wrote empty:", OUT_PATH_MONTHLY)
    else:
        monthly = (
            lines.assign(month=pd.to_datetime(lines["TRN_DATE"], errors="coerce").dt.to_period("M").astype(str))
                 .groupby("month", as_index=False)["NET"].sum()
                 .rename(columns={"NET": "total_cost_pkr"})
                 .sort_values("month")
        )
        monthly.to_csv(OUT_PATH_MONTHLY, index=False)
        print("Wrote monthly costs →", OUT_PATH_MONTHLY)
        print(monthly.tail(12).to_string(index=False))

# --- per-account min/max date over full journal ---
ac_num = ac[["NO","HEAD"]].copy()
ac_num["NO"] = pd.to_numeric(ac_num["NO"], errors="coerce")
jn_valid = jn.dropna(subset=["TRN_DATE","AC_NO"]).copy()

if jn_valid.empty:
    acc_dates = pd.DataFrame(columns=["account_no","name","min_date","max_date","span_days"])
else:
    acc_dates = (
        jn_valid.groupby("AC_NO", as_index=False)["TRN_DATE"]
                .agg(min_date="min", max_date="max")
    )
    acc_dates["span_days"] = (
        pd.to_datetime(acc_dates["max_date"]) - pd.to_datetime(acc_dates["min_date"])
    ).dt.days + 1
    acc_dates = (
        acc_dates.merge(ac_num, left_on="AC_NO", right_on="NO", how="left")
                 .rename(columns={"AC_NO":"account_no","HEAD":"name"})
                 .loc[:, ["account_no","name","min_date","max_date","span_days"]]
                 .sort_values(["span_days","min_date"], ascending=[False, True])
                 .reset_index(drop=True)
    )
acc_dates = acc_dates.drop_duplicates()
acc_dates.to_csv(OUT_PATH_RANGES, index=False)
print("Wrote account date ranges →", OUT_PATH_RANGES)
print(acc_dates.head(25).to_string(index=False))
