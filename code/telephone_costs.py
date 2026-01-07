import pandas as pd
from datetime import date
from pathlib import Path

# --- config ---
ACCOUNT_ID = 30           # e.g., "Telephone Costs"
INCLUDE_CHILDREN = True    # include all descendant accounts via L1–L5 prefix match
ACLIST_PATH = "/Users/osmankhan/Desktop/agro_accounts/ag_data_2014_2025/ACLIST_1425.csv"
JOURNAL_PATH = "/Users/osmankhan/Desktop/agro_accounts/ag_data_2014_2025/JOURNAL_1425.csv"
OUT_PATH = "/Users/osmankhan/Desktop/agro_accounts/ag_data_2014_2025/analysis/salary_costs.csv"
YEARS = 5
# ----------------

# --- load ---
ac = pd.read_csv(ACLIST_PATH, dtype=str, keep_default_na=False)
jn = pd.read_csv(JOURNAL_PATH, dtype=str, keep_default_na=False)

ac.columns = [c.strip().upper() for c in ac.columns]
jn.columns = [c.strip().upper() for c in jn.columns]

# coerce types
for col in ["NO","LEVEL","L1","L2","L3","L4","L5"]:
    if col in ac.columns:
        ac[col] = pd.to_numeric(ac[col], errors="coerce")
ac["HEAD"] = ac.get("HEAD", "").astype(str).str.strip()

jn = jn[["TRN_DATE","AC_NO","DR","CR"]].copy()
jn["TRN_DATE"] = pd.to_datetime(jn["TRN_DATE"], errors="coerce").dt.date
jn["AC_NO"] = pd.to_numeric(jn["AC_NO"], errors="coerce")
jn["DR"] = pd.to_numeric(jn["DR"], errors="coerce").fillna(0)
jn["CR"] = pd.to_numeric(jn["CR"], errors="coerce").fillna(0)

# --- build account filter ---
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

# --- apply to journal ---
lines = jn[jn["AC_NO"].isin(account_ids)].copy()
Path(OUT_PATH).parent.mkdir(parents=True, exist_ok=True)

if lines.empty:
    pd.DataFrame(columns=["month","total_cost_pkr"]).to_csv(OUT_PATH, index=False)
else:
    lines["NET"] = lines["DR"] - lines["CR"]
    today = date.today()
    start = date(today.year - YEARS, today.month, 1)
    lines = lines[(lines["TRN_DATE"] >= start) & (lines["TRN_DATE"] <= today)]

    if lines.empty:
        pd.DataFrame(columns=["month","total_cost_pkr"]).to_csv(OUT_PATH, index=False)
    else:
        monthly = (
            lines.assign(month=pd.to_datetime(lines["TRN_DATE"], errors="coerce").dt.to_period("M").astype(str))
                 .groupby("month", as_index=False)["NET"]
                 .sum()
                 .rename(columns={"NET": "total_cost_pkr"})
                 .sort_values("month")
        )
        monthly.to_csv(OUT_PATH, index=False)
        print(monthly.tail(500).to_string(index=False))