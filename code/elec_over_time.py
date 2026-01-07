# graph_expenses_190_293.py
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

# --- config ---
ACLIST_PATH = "/Users/osmankhan/Desktop/agro_accounts/ag_data_2014_2025/ACLIST_1425.csv"
JOURNAL_PATH = "/Users/osmankhan/Desktop/agro_accounts/ag_data_2014_2025/JOURNAL_1425.csv"
OUT_PATH = Path("/Users/osmankhan/Desktop/agro_accounts/ag_data_2014_2025/analysis/electricity_expense_trend.png")
YEAR_START = 2018
YEAR_END = 2026
ACCOUNT_CODES = [190, 293]  # Electricity, Electricity (Factory)

# --- load ---
ac = pd.read_csv(ACLIST_PATH, dtype=str, keep_default_na=False)
jn = pd.read_csv(JOURNAL_PATH, dtype=str, keep_default_na=False)

ac.columns = [c.strip().upper() for c in ac.columns]
jn.columns = [c.strip().upper() for c in jn.columns]

ac["NO"] = pd.to_numeric(ac.get("NO"), errors="coerce")
ac["HEAD"] = ac.get("HEAD", "").astype(str).str.strip()
jn["TRN_DATE"] = pd.to_datetime(jn.get("TRN_DATE"), errors="coerce")
jn["AC_NO"] = pd.to_numeric(jn.get("AC_NO"), errors="coerce")
jn["DR"] = pd.to_numeric(jn.get("DR", 0), errors="coerce").fillna(0)
jn["CR"] = pd.to_numeric(jn.get("CR", 0), errors="coerce").fillna(0)

# --- merge + compute ---
ac_dim = ac[["NO", "HEAD", "CLASS"]].drop_duplicates()
df = jn.merge(ac_dim, left_on="AC_NO", right_on="NO", how="left")
df["net_expense"] = df["DR"] - df["CR"]
df = df[df["AC_NO"].isin(ACCOUNT_CODES)]
df = df[(df["TRN_DATE"] >= pd.Timestamp(YEAR_START, 1, 1)) & (df["TRN_DATE"] <= pd.Timestamp(YEAR_END, 12, 31))]

# --- monthly trend ---
df["month"] = df["TRN_DATE"].dt.to_period("M").astype(str)
monthly = df.groupby(["month", "HEAD"], as_index=False)["net_expense"].sum()

# --- plot ---
plt.figure(figsize=(9,5))
for head in monthly["HEAD"].unique():
    d = monthly[monthly["HEAD"] == head]
    plt.plot(pd.to_datetime(d["month"] + "-01"), d["net_expense"], marker="o", label=head)

plt.title("Electricity Expense Trends (Accounts 190 & 293)")
plt.xlabel("Month")
plt.ylabel("PKR (DR − CR)")
plt.legend(frameon=False)
plt.grid(True, alpha=0.3)
plt.tight_layout()
OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
plt.savefig(OUT_PATH, dpi=180)
plt.close()

print(f"Wrote chart to {OUT_PATH}")
print(monthly.tail(12))
