# top_expense_accounts.py
# Hardcoded simple version: ranks most expensive accounts (CLASS=4) from 2023 onward.

from pathlib import Path
import pandas as pd

# -------------------
# CONFIG
# -------------------
ACLIST_PATH = "/Users/osmankhan/Desktop/agro_accounts/ag_data_2014_2025/ACLIST_1425.csv"
JOURNAL_PATH = "/Users/osmankhan/Desktop/agro_accounts/ag_data_2014_2025/JOURNAL_1425.csv"
OUT_PATH = Path("/Users/osmankhan/Desktop/agro_accounts/ag_data_2014_2025/analysis/top_expense_accounts.csv")
YEAR_START = 2023
YEAR_END = 2026
TOP_N = 30

# -------------------
# LOAD + CLEAN
# -------------------
ac = pd.read_csv(ACLIST_PATH, dtype=str, keep_default_na=False)
jn = pd.read_csv(JOURNAL_PATH, dtype=str, keep_default_na=False)

ac.columns = [c.strip().upper() for c in ac.columns]
jn.columns = [c.strip().upper() for c in jn.columns]

ac["NO"] = pd.to_numeric(ac.get("NO"), errors="coerce")
ac["CLASS"] = pd.to_numeric(ac.get("CLASS"), errors="coerce")
ac["LEVEL"] = pd.to_numeric(ac.get("LEVEL"), errors="coerce")
ac["HEAD"] = ac.get("HEAD", "").astype(str).str.strip()

jn["TRN_DATE"] = pd.to_datetime(jn.get("TRN_DATE"), errors="coerce")
jn["AC_NO"] = pd.to_numeric(jn.get("AC_NO"), errors="coerce")
jn["DR"] = pd.to_numeric(jn.get("DR", 0), errors="coerce").fillna(0)
jn["CR"] = pd.to_numeric(jn.get("CR", 0), errors="coerce").fillna(0)
jn = jn.dropna(subset=["TRN_DATE", "AC_NO"])

# Deduplicate accounts
ac["_has_head"] = (ac["HEAD"] != "").astype(int)
ac = ac.sort_values(["NO", "LEVEL", "_has_head"], ascending=[True, False, False])
ac_dim = ac.drop_duplicates(subset=["NO"], keep="first")[["NO", "HEAD", "CLASS"]].copy()

# Merge
df = jn.merge(ac_dim, left_on="AC_NO", right_on="NO", how="left", validate="m:1")
df["net_expense"] = df["DR"] - df["CR"]

# -------------------
# FILTER + SUMMARIZE
# -------------------
start = pd.Timestamp(YEAR_START, 1, 1)
end = pd.Timestamp(YEAR_END, 12, 31)
df = df[(df["TRN_DATE"] >= start) & (df["TRN_DATE"] <= end)]
df = df[df["CLASS"] == 4].copy()

grp = (
    df.groupby(["AC_NO", "HEAD"], as_index=False)
      .agg(
          total_spend_pkr=("net_expense", "sum"),
          first_txn=("TRN_DATE", "min"),
          last_txn=("TRN_DATE", "max"),
          months_active=("TRN_DATE", lambda s: s.dt.to_period("M").nunique()),
      )
)
grp["total_spend_pkr"] = grp["total_spend_pkr"].clip(lower=0)
ranked = grp.sort_values("total_spend_pkr", ascending=False).reset_index(drop=True)

OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
ranked.to_csv(OUT_PATH, index=False)

print(f"Wrote: {OUT_PATH}")
print(ranked.head(TOP_N)[["AC_NO", "HEAD", "total_spend_pkr", "months_active", "first_txn", "last_txn"]].to_string(index=False))
